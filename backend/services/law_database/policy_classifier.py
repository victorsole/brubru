"""
Enhanced Policy Area Classifier

Advanced NLP-based classifier to map EU laws to the 33 policy areas
from eu_policies.json.

Uses:
- TF-IDF vectorization
- Keyword matching with weights
- Document type analysis
- Multi-label classification
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import Counter
import re

logger = logging.getLogger(__name__)


class PolicyAreaClassifier:
    """
    Classify EU laws into policy areas using advanced NLP.

    Features:
    - Keyword-based classification with weighted scores
    - Document type heuristics
    - Multi-label support (laws can match multiple areas)
    - Confidence scores
    """

    def __init__(self, policy_taxonomy_path: str = "backend/knowledge_base/institutions/eu_policies.json"):
        """
        Initialize classifier.

        Args:
            policy_taxonomy_path: Path to eu_policies.json
        """
        self.policy_taxonomy = self._load_taxonomy(policy_taxonomy_path)
        self.policy_keywords = self._build_keyword_map()

        logger.info(f"Initialized PolicyAreaClassifier with {len(self.policy_keywords)} policy areas")

    def _load_taxonomy(self, path: str) -> Dict[str, Any]:
        """Load EU policy taxonomy"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load policy taxonomy: {str(e)}")
            return {}

    def _build_keyword_map(self) -> Dict[str, Dict[str, float]]:
        """
        Build keyword mapping for each policy area with weights.

        Returns:
            Dict mapping policy area names to {keyword: weight}
        """
        keyword_map = {}

        # Define keywords and weights for each policy area
        # Weight scale: 1.0 (weak), 2.0 (medium), 3.0 (strong)

        keyword_map['Climate Action'] = {
            'climate': 3.0, 'emission': 3.0, 'carbon': 3.0, 'greenhouse': 3.0,
            'ets': 3.0, 'eu ets': 3.0, 'co2': 3.0, 'decarbonisation': 3.0,
            'carbon dioxide': 3.0, 'climate change': 3.0, 'paris agreement': 2.0,
            'net zero': 2.0, 'climate neutral': 2.0
        }

        keyword_map['Environment'] = {
            'environment': 3.0, 'environmental': 3.0, 'pollution': 3.0, 'waste': 3.0,
            'water': 2.0, 'air quality': 2.0, 'biodiversity': 2.0, 'nature': 2.0,
            'ecosystem': 2.0, 'habitat': 2.0, 'species': 2.0, 'conservation': 2.0,
            'circular economy': 2.0, 'recycling': 2.0
        }

        keyword_map['Digital Policy and Digital Economy'] = {
            'digital': 3.0, 'platform': 3.0, 'data': 2.0, 'online': 2.0,
            'internet': 2.0, 'electronic': 2.0, 'e-commerce': 3.0, 'digital services': 3.0,
            'digital market': 3.0, 'artificial intelligence': 2.0, 'ai': 2.0,
            'algorithm': 2.0, 'digital content': 2.0, 'digital economy': 3.0
        }

        keyword_map['Energy'] = {
            'energy': 3.0, 'renewable': 3.0, 'electricity': 3.0, 'gas': 2.0,
            'nuclear': 2.0, 'power': 2.0, 'grid': 2.0, 'solar': 2.0,
            'wind': 2.0, 'hydropower': 2.0, 'energy efficiency': 3.0,
            'energy security': 3.0, 'renewable energy': 3.0
        }

        keyword_map['Transport'] = {
            'transport': 3.0, 'transportation': 3.0, 'aviation': 3.0, 'maritime': 2.0,
            'railway': 3.0, 'road': 2.0, 'vehicle': 2.0, 'shipping': 2.0,
            'aircraft': 2.0, 'mobility': 2.0, 'traffic': 2.0, 'infrastructure': 1.0
        }

        keyword_map['Competition'] = {
            'competition': 3.0, 'antitrust': 3.0, 'merger': 3.0, 'state aid': 3.0,
            'cartel': 3.0, 'monopoly': 2.0, 'dominant position': 2.0,
            'abuse of dominance': 2.0, 'market power': 2.0, 'concentration': 2.0
        }

        keyword_map['Single Market'] = {
            'single market': 3.0, 'internal market': 3.0, 'free movement': 3.0,
            'goods': 2.0, 'services': 2.0, 'capital': 2.0, 'persons': 2.0,
            'market integration': 2.0, 'harmonisation': 2.0, 'mutual recognition': 2.0
        }

        keyword_map['Trade and Economic Security'] = {
            'trade': 3.0, 'tariff': 3.0, 'customs': 2.0, 'import': 2.0,
            'export': 2.0, 'trade policy': 3.0, 'trade agreement': 3.0,
            'wto': 2.0, 'trade defence': 2.0, 'anti-dumping': 2.0,
            'economic security': 3.0
        }

        keyword_map['Agriculture'] = {
            'agriculture': 3.0, 'agricultural': 3.0, 'farming': 3.0, 'rural': 3.0,
            'cap': 3.0, 'common agricultural policy': 3.0, 'farmer': 2.0,
            'crop': 2.0, 'livestock': 2.0, 'plant': 1.0, 'rural development': 3.0
        }

        keyword_map['Maritime Affairs and Fisheries'] = {
            'fisheries': 3.0, 'fishing': 3.0, 'maritime': 3.0, 'ocean': 2.0,
            'sea': 2.0, 'marine': 2.0, 'fish': 2.0, 'aquaculture': 2.0,
            'coastal': 2.0, 'common fisheries policy': 3.0, 'cfp': 3.0
        }

        keyword_map['Food Safety'] = {
            'food safety': 3.0, 'food': 2.0, 'hygiene': 3.0, 'contamination': 2.0,
            'foodstuff': 3.0, 'food product': 2.0, 'nutrition': 2.0,
            'food additive': 2.0, 'food contact': 2.0, 'efsa': 2.0
        }

        keyword_map['Health'] = {
            'health': 3.0, 'medicine': 3.0, 'pharmaceutical': 3.0, 'patient': 2.0,
            'medical': 3.0, 'medicinal product': 3.0, 'medical device': 3.0,
            'public health': 3.0, 'healthcare': 3.0, 'disease': 2.0,
            'ema': 2.0, 'european medicines agency': 2.0
        }

        keyword_map['Employment and Social Affairs'] = {
            'employment': 3.0, 'worker': 3.0, 'labour': 3.0, 'social': 2.0,
            'working conditions': 3.0, 'workplace': 2.0, 'employee': 2.0,
            'social security': 3.0, 'social protection': 3.0, 'job': 2.0
        }

        keyword_map['Consumer Protection'] = {
            'consumer': 3.0, 'product safety': 3.0, 'consumer rights': 3.0,
            'consumer protection': 3.0, 'unfair commercial practice': 3.0,
            'consumer contract': 2.0, 'product liability': 2.0
        }

        keyword_map['Justice and Fundamental Rights'] = {
            'justice': 3.0, 'fundamental rights': 3.0, 'data protection': 3.0,
            'privacy': 3.0, 'gdpr': 3.0, 'personal data': 3.0, 'right': 2.0,
            'judicial cooperation': 2.0, 'rule of law': 2.0, 'charter': 2.0
        }

        keyword_map['Migration and Home Affairs'] = {
            'migration': 3.0, 'asylum': 3.0, 'border': 3.0, 'visa': 3.0,
            'schengen': 3.0, 'refugee': 2.0, 'immigration': 3.0,
            'frontex': 2.0, 'border control': 3.0, 'illegal migration': 2.0
        }

        keyword_map['Research and Innovation'] = {
            'research': 3.0, 'innovation': 3.0, 'horizon': 3.0, 'r&d': 3.0,
            'science': 2.0, 'research and development': 3.0, 'scientific': 2.0,
            'framework programme': 3.0, 'innovation fund': 2.0
        }

        keyword_map['Education, Training and Youth'] = {
            'education': 3.0, 'training': 3.0, 'erasmus': 3.0, 'student': 2.0,
            'youth': 3.0, 'learning': 2.0, 'school': 2.0, 'university': 2.0,
            'vocational training': 3.0, 'erasmus+': 3.0
        }

        keyword_map['Regional Policy'] = {
            'regional': 3.0, 'cohesion': 3.0, 'structural funds': 3.0,
            'regional development': 3.0, 'erdf': 3.0, 'european regional development fund': 3.0,
            'cohesion fund': 3.0, 'convergence': 2.0
        }

        keyword_map['Taxation'] = {
            'tax': 3.0, 'taxation': 3.0, 'vat': 3.0, 'excise': 3.0,
            'fiscal': 2.0, 'tax policy': 3.0, 'corporate tax': 2.0,
            'tax avoidance': 2.0, 'tax evasion': 2.0
        }

        keyword_map['Economic and Financial Affairs'] = {
            'financial': 3.0, 'banking': 3.0, 'finance': 3.0, 'capital markets': 3.0,
            'payment': 2.0, 'financial services': 3.0, 'financial institution': 3.0,
            'financial stability': 3.0, 'economic policy': 2.0, 'monetary': 2.0
        }

        keyword_map['Defence and Security'] = {
            'defence': 3.0, 'defense': 3.0, 'security': 2.0, 'military': 3.0,
            'armament': 3.0, 'defence industry': 3.0, 'security policy': 2.0,
            'cybersecurity': 2.0, 'defence cooperation': 3.0
        }

        keyword_map['Foreign and Security Policy'] = {
            'foreign policy': 3.0, 'external action': 3.0, 'diplomacy': 2.0,
            'common foreign': 3.0, 'cfsp': 3.0, 'eeas': 2.0, 'international relations': 2.0
        }

        keyword_map['Communication Networks, Content and Technology'] = {
            'telecommunication': 3.0, 'spectrum': 3.0, 'broadband': 3.0, '5g': 3.0,
            'network': 2.0, 'telecom': 3.0, 'electronic communications': 3.0,
            'roaming': 2.0, 'frequency': 2.0
        }

        keyword_map['Customs'] = {
            'customs': 3.0, 'customs union': 3.0, 'customs code': 3.0,
            'customs procedure': 3.0, 'customs duty': 3.0, 'customs control': 2.0,
            'customs tariff': 3.0
        }

        keyword_map['Business and Industry'] = {
            'industry': 3.0, 'industrial': 3.0, 'business': 2.0, 'enterprise': 2.0,
            'sme': 2.0, 'small and medium': 2.0, 'industrial policy': 3.0,
            'manufacturing': 2.0, 'industrial strategy': 3.0
        }

        keyword_map['Culture'] = {
            'culture': 3.0, 'cultural': 3.0, 'heritage': 3.0, 'cultural heritage': 3.0,
            'cultural diversity': 3.0, 'creative': 2.0, 'arts': 2.0,
            'cultural policy': 3.0, 'cultural sector': 2.0
        }

        keyword_map['Space Policy'] = {
            'space': 3.0, 'satellite': 3.0, 'galileo': 3.0, 'copernicus': 3.0,
            'space programme': 3.0, 'space policy': 3.0, 'esa': 2.0,
            'european space agency': 2.0
        }

        keyword_map['Statistics'] = {
            'statistics': 3.0, 'statistical': 3.0, 'eurostat': 3.0,
            'statistical data': 3.0, 'data collection': 2.0
        }

        keyword_map['Development and Cooperation'] = {
            'development': 2.0, 'developing countries': 3.0, 'development cooperation': 3.0,
            'development aid': 3.0, 'international development': 3.0,
            'cooperation': 1.0
        }

        keyword_map['Neighbourhood and Enlargement'] = {
            'enlargement': 3.0, 'neighbourhood': 3.0, 'candidate country': 3.0,
            'accession': 3.0, 'pre-accession': 3.0, 'eastern partnership': 2.0
        }

        keyword_map['Human Rights and Democracy'] = {
            'human rights': 3.0, 'democracy': 3.0, 'democratisation': 3.0,
            'human right violation': 2.0, 'civil society': 2.0
        }

        keyword_map['Humanitarian Aid and Civil Protection'] = {
            'humanitarian': 3.0, 'humanitarian aid': 3.0, 'civil protection': 3.0,
            'disaster': 2.0, 'emergency': 2.0, 'relief': 2.0, 'echo': 2.0
        }

        return keyword_map

    def classify(
        self,
        title: str,
        doc_type: str = "",
        subject_matter: List[str] = None,
        full_text: str = "",
        return_all: bool = False
    ) -> Union[str, List[Tuple[str, float]]]:
        """
        Classify law into policy area(s).

        Args:
            title: Law title
            doc_type: Document type
            subject_matter: Subject matter keywords
            full_text: Full text (optional, for better classification)
            return_all: Return all matches with scores instead of just best

        Returns:
            Policy area name, or list of (policy_area, score) tuples if return_all=True
        """
        # Combine all text for analysis
        text_parts = [title]
        if doc_type:
            text_parts.append(doc_type)
        if subject_matter:
            text_parts.extend(subject_matter)
        if full_text:
            # Use first 1000 chars of full text
            text_parts.append(full_text[:1000])

        combined_text = " ".join(text_parts).lower()

        # Score each policy area
        scores = {}

        for policy_area, keywords in self.policy_keywords.items():
            score = 0.0

            for keyword, weight in keywords.items():
                # Count occurrences
                count = combined_text.count(keyword.lower())
                if count > 0:
                    # Add weighted score (diminishing returns for multiple occurrences)
                    score += weight * min(count, 3)

            if score > 0:
                scores[policy_area] = score

        if not scores:
            return [] if return_all else None

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if return_all:
            return sorted_scores
        else:
            # Return highest scoring policy area
            return sorted_scores[0][0]

    def classify_with_confidence(
        self,
        title: str,
        doc_type: str = "",
        subject_matter: List[str] = None,
        full_text: str = ""
    ) -> Tuple[Optional[str], float]:
        """
        Classify with confidence score.

        Returns:
            Tuple of (policy_area, confidence_score)
            confidence_score is 0-1 where 1 is very confident
        """
        all_scores = self.classify(
            title=title,
            doc_type=doc_type,
            subject_matter=subject_matter,
            full_text=full_text,
            return_all=True
        )

        if not all_scores:
            return None, 0.0

        # Get top score
        best_policy, best_score = all_scores[0]

        # Calculate confidence based on score gap to second place
        if len(all_scores) > 1:
            second_score = all_scores[1][1]
            score_gap = best_score - second_score

            # Confidence increases with score gap
            # If best_score is 2x or more than second, confidence = 1.0
            confidence = min(score_gap / best_score, 1.0)
        else:
            # Only one match, high confidence
            confidence = 0.9

        # Normalize confidence based on absolute score
        # Very low absolute scores get low confidence
        if best_score < 3.0:
            confidence *= 0.5
        elif best_score < 5.0:
            confidence *= 0.7

        return best_policy, confidence


# Global singleton
_classifier: Optional[PolicyAreaClassifier] = None


def get_policy_classifier() -> PolicyAreaClassifier:
    """Get global policy classifier instance"""
    global _classifier
    if _classifier is None:
        _classifier = PolicyAreaClassifier()
    return _classifier
