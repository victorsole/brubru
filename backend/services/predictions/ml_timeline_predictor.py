"""
ML Timeline Predictor - Phase 2.1

XGBoost-based timeline prediction with confidence intervals.

Extends the baseline TimelinePredictor with ML capabilities:
- Feature-based prediction using XGBoost regressor
- Quantile regression for confidence intervals
- Model persistence and retraining

Usage:
    predictor = MLTimelinePredictor()
    prediction = await predictor.predict_with_ml(procedure_ref)
    await predictor.train_model(training_data_path)
"""

import os
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

import numpy as np

from sqlalchemy.orm import Session

from core.database import SessionLocal
from .timeline_predictor import TimelinePredictor, TimelinePrediction
from .feature_extractor import FeatureExtractor, CarriageFeatures, get_feature_extractor

logger = logging.getLogger(__name__)

# Default model path
DEFAULT_MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"


@dataclass
class MLPrediction:
    """
    ML-based timeline prediction with confidence intervals.
    """
    procedure_ref: str
    current_status: str
    days_in_status: int

    # Point prediction
    predicted_days_remaining: int
    confidence: float  # 0.0-1.0

    # Confidence intervals (quantile predictions)
    lower_bound_25: Optional[int] = None  # 25th percentile
    upper_bound_75: Optional[int] = None  # 75th percentile
    lower_bound_10: Optional[int] = None  # 10th percentile
    upper_bound_90: Optional[int] = None  # 90th percentile

    # Model info
    model_version: str = "1.0"
    features_used: List[str] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Fallback info
    used_fallback: bool = False
    fallback_reason: Optional[str] = None


class MLTimelinePredictor:
    """
    XGBoost-based timeline predictor with quantile regression.

    Usage:
        predictor = MLTimelinePredictor()

        # Train model (one-time or periodic)
        await predictor.train_model("data/ml/training_timeline.csv")

        # Predict
        prediction = await predictor.predict_with_ml(procedure_ref)
    """

    # Feature columns used for training (categorical will be encoded)
    CATEGORICAL_FEATURES = [
        'procedure_type', 'text_type', 'lead_committee', 'current_status'
    ]

    NUMERIC_FEATURES = [
        'days_in_current_status', 'days_since_first_seen', 'month_of_year',
        'quarter', 'num_opinion_committees', 'total_committees',
        'num_status_changes', 'avg_days_per_status', 'title_length',
        'title_word_count', 'num_celex_refs', 'num_policy_areas',
        'is_recast', 'is_codification', 'has_rapporteur', 'is_election_year',
        'is_pre_summer_break', 'is_end_of_term', 'has_celex', 'has_eprs_briefing',
        'is_spotlight'
    ]

    def __init__(
        self,
        db: Optional[Session] = None,
        model_dir: Optional[Path] = None
    ):
        self._db = db
        self._owns_db = db is None
        self.model_dir = model_dir or DEFAULT_MODEL_DIR

        # Models (lazy loaded)
        self._model = None
        self._model_lower = None  # 25th percentile
        self._model_upper = None  # 75th percentile
        self._label_encoders = {}
        self._model_version = "1.0"
        self._feature_names = []

        # Fallback predictor
        self._fallback_predictor = None

        # Feature extractor
        self._extractor = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def extractor(self) -> FeatureExtractor:
        if self._extractor is None:
            self._extractor = FeatureExtractor(self.db)
        return self._extractor

    @property
    def fallback_predictor(self) -> TimelinePredictor:
        if self._fallback_predictor is None:
            self._fallback_predictor = TimelinePredictor(self.db)
        return self._fallback_predictor

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _get_model_path(self, name: str) -> Path:
        """Get path for a model file."""
        return self.model_dir / f"{name}.pkl"

    def _load_models(self) -> bool:
        """
        Load trained models from disk.

        Returns True if models loaded successfully.
        """
        try:
            main_path = self._get_model_path("timeline_xgb")
            lower_path = self._get_model_path("timeline_xgb_q25")
            upper_path = self._get_model_path("timeline_xgb_q75")
            encoders_path = self._get_model_path("timeline_encoders")
            meta_path = self._get_model_path("timeline_meta")

            if not main_path.exists():
                logger.info("No trained model found")
                return False

            with open(main_path, 'rb') as f:
                self._model = pickle.load(f)

            if lower_path.exists():
                with open(lower_path, 'rb') as f:
                    self._model_lower = pickle.load(f)

            if upper_path.exists():
                with open(upper_path, 'rb') as f:
                    self._model_upper = pickle.load(f)

            if encoders_path.exists():
                with open(encoders_path, 'rb') as f:
                    self._label_encoders = pickle.load(f)

            if meta_path.exists():
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                    self._model_version = meta.get('version', '1.0')
                    self._feature_names = meta.get('feature_names', [])

            logger.info(f"Loaded timeline model v{self._model_version}")
            return True

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False

    def _save_models(self):
        """Save trained models to disk."""
        self.model_dir.mkdir(parents=True, exist_ok=True)

        with open(self._get_model_path("timeline_xgb"), 'wb') as f:
            pickle.dump(self._model, f)

        if self._model_lower:
            with open(self._get_model_path("timeline_xgb_q25"), 'wb') as f:
                pickle.dump(self._model_lower, f)

        if self._model_upper:
            with open(self._get_model_path("timeline_xgb_q75"), 'wb') as f:
                pickle.dump(self._model_upper, f)

        with open(self._get_model_path("timeline_encoders"), 'wb') as f:
            pickle.dump(self._label_encoders, f)

        meta = {
            'version': self._model_version,
            'feature_names': self._feature_names,
            'trained_at': datetime.now(timezone.utc).isoformat()
        }
        with open(self._get_model_path("timeline_meta"), 'wb') as f:
            pickle.dump(meta, f)

        logger.info(f"Saved timeline model v{self._model_version}")

    def _prepare_features(self, features: CarriageFeatures) -> Optional[np.ndarray]:
        """
        Convert CarriageFeatures to numpy array for prediction.

        Applies label encoding to categorical features.
        """
        try:
            from sklearn.preprocessing import LabelEncoder

            feature_dict = features.to_dict()
            feature_values = []

            # Process numeric features
            for feat in self.NUMERIC_FEATURES:
                val = feature_dict.get(feat, 0)
                if isinstance(val, bool):
                    val = 1.0 if val else 0.0
                feature_values.append(float(val) if val is not None else 0.0)

            # Process categorical features
            for feat in self.CATEGORICAL_FEATURES:
                val = str(feature_dict.get(feat, 'UNKNOWN'))

                if feat in self._label_encoders:
                    encoder = self._label_encoders[feat]
                    # Handle unseen categories
                    if val in encoder.classes_:
                        encoded = encoder.transform([val])[0]
                    else:
                        # Use -1 for unknown categories
                        encoded = -1
                else:
                    encoded = 0

                feature_values.append(float(encoded))

            return np.array([feature_values])

        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None

    async def train_model(
        self,
        training_data_path: str,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Train XGBoost models on exported training data.

        Args:
            training_data_path: Path to training CSV from export_training_data.py
            test_size: Fraction for test split
            random_state: Random seed for reproducibility

        Returns:
            Training metrics dictionary
        """
        try:
            import pandas as pd
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import LabelEncoder
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            import xgboost as xgb

            logger.info(f"Loading training data from {training_data_path}")

            # Load data
            df = pd.read_csv(training_data_path)
            logger.info(f"Loaded {len(df)} training samples")

            if len(df) < 50:
                return {'error': 'Insufficient training data (need >= 50 samples)'}

            # Prepare target
            y = df['days_in_status'].values

            # Prepare features
            X_numeric = df[self.NUMERIC_FEATURES].fillna(0).values

            # Encode categorical features
            X_categorical = []
            self._label_encoders = {}

            for feat in self.CATEGORICAL_FEATURES:
                if feat in df.columns:
                    encoder = LabelEncoder()
                    encoded = encoder.fit_transform(df[feat].fillna('UNKNOWN').astype(str))
                    X_categorical.append(encoded.reshape(-1, 1))
                    self._label_encoders[feat] = encoder
                else:
                    X_categorical.append(np.zeros((len(df), 1)))

            X_categorical = np.hstack(X_categorical)
            X = np.hstack([X_numeric, X_categorical])

            self._feature_names = self.NUMERIC_FEATURES + self.CATEGORICAL_FEATURES

            # Train/test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )

            logger.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")

            # Train main model (median prediction)
            logger.info("Training main XGBoost model...")
            self._model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='reg:squarederror',
                random_state=random_state
            )
            self._model.fit(X_train, y_train)

            # Train quantile models for confidence intervals
            logger.info("Training quantile models...")

            # 25th percentile (lower bound)
            self._model_lower = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='reg:quantileerror',
                quantile_alpha=0.25,
                random_state=random_state
            )
            self._model_lower.fit(X_train, y_train)

            # 75th percentile (upper bound)
            self._model_upper = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='reg:quantileerror',
                quantile_alpha=0.75,
                random_state=random_state
            )
            self._model_upper.fit(X_train, y_train)

            # Evaluate
            y_pred = self._model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            # Feature importance
            importance = dict(zip(
                self._feature_names,
                self._model.feature_importances_
            ))
            top_features = sorted(importance.items(), key=lambda x: -x[1])[:10]

            # Update version
            self._model_version = datetime.now().strftime("%Y%m%d")

            # Save models
            self._save_models()

            metrics = {
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'mae': round(mae, 2),
                'rmse': round(rmse, 2),
                'r2': round(r2, 4),
                'top_features': top_features,
                'model_version': self._model_version
            }

            logger.info(f"[OK] Training complete. MAE: {mae:.2f} days, R2: {r2:.4f}")
            return metrics

        except ImportError as e:
            return {'error': f'Missing dependency: {e}'}
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {'error': str(e)}

    async def predict_with_ml(
        self,
        procedure_ref: str
    ) -> MLPrediction:
        """
        Predict timeline using ML model with fallback to baseline.

        Args:
            procedure_ref: OEIL procedure reference or carriage ID

        Returns:
            MLPrediction with confidence intervals
        """
        # Load models if not loaded
        if self._model is None:
            if not self._load_models():
                # Fall back to baseline predictor
                baseline = await self.fallback_predictor.predict_timeline(procedure_ref)
                if baseline:
                    return MLPrediction(
                        procedure_ref=procedure_ref,
                        current_status=baseline.current_status,
                        days_in_status=baseline.days_in_status,
                        predicted_days_remaining=baseline.predicted_days_remaining or 0,
                        confidence=baseline.confidence,
                        used_fallback=True,
                        fallback_reason="No trained ML model available"
                    )
                return MLPrediction(
                    procedure_ref=procedure_ref,
                    current_status="unknown",
                    days_in_status=0,
                    predicted_days_remaining=0,
                    confidence=0.0,
                    used_fallback=True,
                    fallback_reason="Procedure not found"
                )

        try:
            from models.legislative_train import LegislativeCarriage
            from sqlalchemy import or_

            # Get carriage
            carriage = self.db.query(LegislativeCarriage).filter(
                or_(
                    LegislativeCarriage.oeil_procedure_ref == procedure_ref,
                    LegislativeCarriage.id == procedure_ref
                )
            ).first()

            if not carriage:
                return MLPrediction(
                    procedure_ref=procedure_ref,
                    current_status="unknown",
                    days_in_status=0,
                    predicted_days_remaining=0,
                    confidence=0.0,
                    used_fallback=True,
                    fallback_reason="Procedure not found"
                )

            # Extract features
            features = self.extractor.extract_features(carriage)

            # Prepare feature array
            X = self._prepare_features(features)
            if X is None:
                baseline = await self.fallback_predictor.predict_timeline(procedure_ref)
                return MLPrediction(
                    procedure_ref=procedure_ref,
                    current_status=features.current_status,
                    days_in_status=features.days_in_current_status,
                    predicted_days_remaining=baseline.predicted_days_remaining if baseline else 0,
                    confidence=0.3,
                    used_fallback=True,
                    fallback_reason="Feature extraction failed"
                )

            # Predict
            pred_main = max(0, int(self._model.predict(X)[0]))

            # Quantile predictions
            lower_25 = None
            upper_75 = None
            if self._model_lower and self._model_upper:
                lower_25 = max(0, int(self._model_lower.predict(X)[0]))
                upper_75 = max(0, int(self._model_upper.predict(X)[0]))

            # Adjust for days already spent
            days_in_status = features.days_in_current_status
            pred_remaining = max(0, pred_main - days_in_status)

            if lower_25 is not None:
                lower_25 = max(0, lower_25 - days_in_status)
            if upper_75 is not None:
                upper_75 = max(0, upper_75 - days_in_status)

            # Calculate confidence based on feature coverage
            confidence = 0.7  # Base confidence for ML prediction
            if features.procedure_type == "UNKNOWN":
                confidence -= 0.1
            if features.lead_committee == "UNKNOWN":
                confidence -= 0.1

            # Get feature importance for this prediction
            feature_importance = {}
            if hasattr(self._model, 'feature_importances_'):
                for i, name in enumerate(self._feature_names):
                    if i < len(self._model.feature_importances_):
                        feature_importance[name] = float(self._model.feature_importances_[i])

            return MLPrediction(
                procedure_ref=procedure_ref,
                current_status=features.current_status,
                days_in_status=days_in_status,
                predicted_days_remaining=pred_remaining,
                confidence=confidence,
                lower_bound_25=lower_25,
                upper_bound_75=upper_75,
                model_version=self._model_version,
                features_used=self._feature_names,
                feature_importance=feature_importance
            )

        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            baseline = await self.fallback_predictor.predict_timeline(procedure_ref)
            return MLPrediction(
                procedure_ref=procedure_ref,
                current_status=baseline.current_status if baseline else "unknown",
                days_in_status=baseline.days_in_status if baseline else 0,
                predicted_days_remaining=baseline.predicted_days_remaining if baseline else 0,
                confidence=baseline.confidence if baseline else 0.0,
                used_fallback=True,
                fallback_reason=str(e)
            )

    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        if self._model is None:
            self._load_models()

        if self._model is None:
            return {'status': 'not_trained', 'message': 'No model available'}

        info = {
            'status': 'ready',
            'version': self._model_version,
            'feature_count': len(self._feature_names),
            'features': self._feature_names,
            'has_quantile_models': self._model_lower is not None,
        }

        if hasattr(self._model, 'feature_importances_'):
            importance = dict(zip(
                self._feature_names,
                self._model.feature_importances_
            ))
            info['top_features'] = sorted(
                importance.items(),
                key=lambda x: -x[1]
            )[:10]

        return info


# Singleton instance
_ml_predictor_instance: Optional[MLTimelinePredictor] = None


def get_ml_timeline_predictor() -> MLTimelinePredictor:
    """Get or create the ML timeline predictor instance."""
    global _ml_predictor_instance
    if _ml_predictor_instance is None:
        _ml_predictor_instance = MLTimelinePredictor()
    return _ml_predictor_instance
