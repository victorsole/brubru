"""
Outcome Predictor - Phase 2.2

XGBoost-based legislative outcome prediction.

Predicts the final outcome of a legislative procedure:
- adopted: Procedure successfully adopted
- amended_significantly: Adopted with major changes (future enhancement)
- blocked: Stalled in legislative process
- withdrawn: Commission withdrew the proposal

Usage:
    predictor = OutcomePredictor()
    prediction = await predictor.predict_outcome(procedure_ref)
    await predictor.train_model(training_data_path)
"""

import os
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import numpy as np

from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.database import SessionLocal
from .feature_extractor import FeatureExtractor, CarriageFeatures, get_feature_extractor

logger = logging.getLogger(__name__)

# Default model path
DEFAULT_MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"

# Outcome classes
OUTCOME_CLASSES = ['adopted', 'blocked', 'withdrawn']


@dataclass
class OutcomeProbability:
    """Probability for a single outcome class."""
    outcome: str
    probability: float
    description: str = ""


@dataclass
class OutcomePrediction:
    """
    Outcome prediction with probabilities for each class.
    """
    procedure_ref: str
    current_status: str

    # Predicted outcome
    predicted_outcome: str
    confidence: float  # Probability of predicted class

    # All class probabilities
    probabilities: List[OutcomeProbability] = field(default_factory=list)

    # Model info
    model_version: str = "1.0"
    features_used: List[str] = field(default_factory=list)
    top_factors: List[Dict[str, Any]] = field(default_factory=list)

    # Fallback info
    used_fallback: bool = False
    fallback_reason: Optional[str] = None


class OutcomePredictor:
    """
    XGBoost-based outcome classifier.

    Predicts the final outcome of legislative procedures.

    Usage:
        predictor = OutcomePredictor()

        # Train model (one-time or periodic)
        await predictor.train_model("data/ml/training_outcome.csv")

        # Predict
        prediction = await predictor.predict_outcome(procedure_ref)
    """

    # Feature columns (same as timeline predictor for consistency)
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

    # Outcome descriptions
    OUTCOME_DESCRIPTIONS = {
        'adopted': 'Procedure successfully completes legislative process',
        'blocked': 'Procedure stalls without formal withdrawal',
        'withdrawn': 'Commission formally withdraws the proposal',
    }

    def __init__(
        self,
        db: Optional[Session] = None,
        model_dir: Optional[Path] = None
    ):
        self._db = db
        self._owns_db = db is None
        self.model_dir = model_dir or DEFAULT_MODEL_DIR

        # Model (lazy loaded)
        self._model = None
        self._label_encoders = {}
        self._class_labels = OUTCOME_CLASSES
        self._model_version = "1.0"
        self._feature_names = []

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

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _get_model_path(self, name: str) -> Path:
        """Get path for a model file."""
        return self.model_dir / f"{name}.pkl"

    def _load_model(self) -> bool:
        """
        Load trained model from disk.

        Returns True if model loaded successfully.
        """
        try:
            model_path = self._get_model_path("outcome_xgb")
            encoders_path = self._get_model_path("outcome_encoders")
            meta_path = self._get_model_path("outcome_meta")

            if not model_path.exists():
                logger.info("No trained outcome model found")
                return False

            with open(model_path, 'rb') as f:
                self._model = pickle.load(f)

            if encoders_path.exists():
                with open(encoders_path, 'rb') as f:
                    self._label_encoders = pickle.load(f)

            if meta_path.exists():
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                    self._model_version = meta.get('version', '1.0')
                    self._feature_names = meta.get('feature_names', [])
                    self._class_labels = meta.get('class_labels', OUTCOME_CLASSES)

            logger.info(f"Loaded outcome model v{self._model_version}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def _save_model(self):
        """Save trained model to disk."""
        self.model_dir.mkdir(parents=True, exist_ok=True)

        with open(self._get_model_path("outcome_xgb"), 'wb') as f:
            pickle.dump(self._model, f)

        with open(self._get_model_path("outcome_encoders"), 'wb') as f:
            pickle.dump(self._label_encoders, f)

        meta = {
            'version': self._model_version,
            'feature_names': self._feature_names,
            'class_labels': self._class_labels,
            'trained_at': datetime.now(timezone.utc).isoformat()
        }
        with open(self._get_model_path("outcome_meta"), 'wb') as f:
            pickle.dump(meta, f)

        logger.info(f"Saved outcome model v{self._model_version}")

    def _prepare_features(self, features: CarriageFeatures) -> Optional[np.ndarray]:
        """
        Convert CarriageFeatures to numpy array for prediction.
        """
        try:
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
                    if val in encoder.classes_:
                        encoded = encoder.transform([val])[0]
                    else:
                        encoded = -1
                else:
                    encoded = 0

                feature_values.append(float(encoded))

            return np.array([feature_values])

        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None

    def _get_baseline_prediction(self, features: CarriageFeatures) -> OutcomePrediction:
        """
        Simple rule-based prediction as fallback.
        """
        # Simple heuristics based on status and time
        current_status = features.current_status.lower()
        days_in_status = features.days_in_current_status

        # Default probabilities
        probs = {'adopted': 0.6, 'blocked': 0.25, 'withdrawn': 0.15}

        # Adjust based on current status
        if current_status in ('close_to_adoption', 'completed'):
            probs = {'adopted': 0.85, 'blocked': 0.10, 'withdrawn': 0.05}
        elif current_status == 'blocked':
            probs = {'adopted': 0.20, 'blocked': 0.60, 'withdrawn': 0.20}
        elif current_status == 'announced':
            # Early stage - higher withdrawal risk
            probs = {'adopted': 0.50, 'blocked': 0.25, 'withdrawn': 0.25}

        # Adjust for stagnation
        if days_in_status > 365:
            probs['blocked'] += 0.15
            probs['adopted'] -= 0.10
            probs['withdrawn'] += 0.05

        # Normalize
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}

        # Get predicted class
        predicted = max(probs.items(), key=lambda x: x[1])

        return OutcomePrediction(
            procedure_ref=features.procedure_ref or features.carriage_id,
            current_status=features.current_status,
            predicted_outcome=predicted[0],
            confidence=predicted[1],
            probabilities=[
                OutcomeProbability(
                    outcome=k,
                    probability=v,
                    description=self.OUTCOME_DESCRIPTIONS.get(k, '')
                )
                for k, v in sorted(probs.items(), key=lambda x: -x[1])
            ],
            used_fallback=True,
            fallback_reason="Using rule-based baseline"
        )

    async def train_model(
        self,
        training_data_path: str,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Train XGBoost classifier on exported training data.

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
            from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
            import xgboost as xgb

            logger.info(f"Loading training data from {training_data_path}")

            # Load data
            df = pd.read_csv(training_data_path)
            logger.info(f"Loaded {len(df)} training samples")

            if len(df) < 50:
                return {'error': 'Insufficient training data (need >= 50 samples)'}

            # Filter to valid outcomes
            df = df[df['outcome'].isin(OUTCOME_CLASSES)]
            logger.info(f"After filtering: {len(df)} samples with valid outcomes")

            # Check class distribution
            class_counts = df['outcome'].value_counts()
            logger.info(f"Class distribution:\n{class_counts}")

            # Prepare target
            y_encoder = LabelEncoder()
            y = y_encoder.fit_transform(df['outcome'])
            self._class_labels = list(y_encoder.classes_)

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

            # Train/test split with stratification
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y
            )

            logger.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")

            # Calculate class weights for imbalanced data
            class_weights = len(y_train) / (len(self._class_labels) * np.bincount(y_train))
            sample_weights = class_weights[y_train]

            # Train XGBoost classifier
            logger.info("Training XGBoost classifier...")
            self._model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='multi:softprob',
                num_class=len(self._class_labels),
                random_state=random_state,
                use_label_encoder=False,
                eval_metric='mlogloss'
            )
            self._model.fit(X_train, y_train, sample_weight=sample_weights)

            # Evaluate
            y_pred = self._model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Detailed classification report
            report = classification_report(
                y_test, y_pred,
                target_names=self._class_labels,
                output_dict=True
            )

            # Confusion matrix
            cm = confusion_matrix(y_test, y_pred)

            # Feature importance
            importance = dict(zip(
                self._feature_names,
                self._model.feature_importances_
            ))
            top_features = sorted(importance.items(), key=lambda x: -x[1])[:10]

            # Update version
            self._model_version = datetime.now().strftime("%Y%m%d")

            # Save model
            self._save_model()

            metrics = {
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'accuracy': round(accuracy, 4),
                'class_report': {
                    k: {m: round(v, 4) for m, v in class_metrics.items()}
                    for k, class_metrics in report.items()
                    if k in self._class_labels
                },
                'confusion_matrix': cm.tolist(),
                'top_features': top_features,
                'model_version': self._model_version
            }

            logger.info(f"[OK] Training complete. Accuracy: {accuracy:.4f}")
            return metrics

        except ImportError as e:
            return {'error': f'Missing dependency: {e}'}
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {'error': str(e)}

    async def predict_outcome(
        self,
        procedure_ref: str
    ) -> OutcomePrediction:
        """
        Predict outcome using ML model with fallback to baseline.

        Args:
            procedure_ref: OEIL procedure reference or carriage ID

        Returns:
            OutcomePrediction with class probabilities
        """
        # Load model if not loaded
        if self._model is None:
            self._load_model()

        try:
            from models.legislative_train import LegislativeCarriage

            # Get carriage
            carriage = self.db.query(LegislativeCarriage).filter(
                or_(
                    LegislativeCarriage.oeil_procedure_ref == procedure_ref,
                    LegislativeCarriage.id == procedure_ref
                )
            ).first()

            if not carriage:
                return OutcomePrediction(
                    procedure_ref=procedure_ref,
                    current_status="unknown",
                    predicted_outcome="adopted",
                    confidence=0.0,
                    used_fallback=True,
                    fallback_reason="Procedure not found"
                )

            # Extract features
            features = self.extractor.extract_features(carriage)

            # If no model, use baseline
            if self._model is None:
                return self._get_baseline_prediction(features)

            # Prepare feature array
            X = self._prepare_features(features)
            if X is None:
                return self._get_baseline_prediction(features)

            # Predict probabilities
            probs = self._model.predict_proba(X)[0]

            # Build probability list
            prob_list = []
            for i, label in enumerate(self._class_labels):
                prob_list.append(OutcomeProbability(
                    outcome=label,
                    probability=float(probs[i]),
                    description=self.OUTCOME_DESCRIPTIONS.get(label, '')
                ))

            # Sort by probability
            prob_list.sort(key=lambda x: -x.probability)

            # Get predicted class
            predicted_idx = np.argmax(probs)
            predicted_outcome = self._class_labels[predicted_idx]
            confidence = float(probs[predicted_idx])

            # Get top factors (features with highest importance)
            top_factors = []
            if hasattr(self._model, 'feature_importances_'):
                importance = list(zip(
                    self._feature_names,
                    self._model.feature_importances_
                ))
                importance.sort(key=lambda x: -x[1])

                for feat_name, feat_imp in importance[:5]:
                    # Get the actual feature value
                    feat_dict = features.to_dict()
                    feat_value = feat_dict.get(feat_name, 'N/A')
                    top_factors.append({
                        'feature': feat_name,
                        'importance': float(feat_imp),
                        'value': feat_value
                    })

            return OutcomePrediction(
                procedure_ref=procedure_ref,
                current_status=features.current_status,
                predicted_outcome=predicted_outcome,
                confidence=confidence,
                probabilities=prob_list,
                model_version=self._model_version,
                features_used=self._feature_names,
                top_factors=top_factors
            )

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            # Try to get features for baseline
            try:
                from models.legislative_train import LegislativeCarriage
                carriage = self.db.query(LegislativeCarriage).filter(
                    or_(
                        LegislativeCarriage.oeil_procedure_ref == procedure_ref,
                        LegislativeCarriage.id == procedure_ref
                    )
                ).first()
                if carriage:
                    features = self.extractor.extract_features(carriage)
                    result = self._get_baseline_prediction(features)
                    result.fallback_reason = str(e)
                    return result
            except Exception:
                pass

            return OutcomePrediction(
                procedure_ref=procedure_ref,
                current_status="unknown",
                predicted_outcome="adopted",
                confidence=0.0,
                used_fallback=True,
                fallback_reason=str(e)
            )

    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        if self._model is None:
            self._load_model()

        if self._model is None:
            return {'status': 'not_trained', 'message': 'No model available'}

        info = {
            'status': 'ready',
            'version': self._model_version,
            'classes': self._class_labels,
            'feature_count': len(self._feature_names),
            'features': self._feature_names,
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
_outcome_predictor_instance: Optional[OutcomePredictor] = None


def get_outcome_predictor() -> OutcomePredictor:
    """Get or create the outcome predictor instance."""
    global _outcome_predictor_instance
    if _outcome_predictor_instance is None:
        _outcome_predictor_instance = OutcomePredictor()
    return _outcome_predictor_instance
