<?php

namespace WPML\WPSEO\RankMathSEO\TranslationJob;

use WPML\WPSEO\Shared\TranslationJob\BaseHooks;

class Hooks extends BaseHooks {

	const OPTION_PREFIX = 'rank-math-';

	/**
	 * @inheritDoc
	 */
	protected function getFieldPrefix() {
		return 'field-rank_math_';
	}

	/**
	 * @inheritDoc
	 */
	protected function getTopLevelGroup() {
		return [ self::OPTION_PREFIX => 'Rank Math SEO' ];
	}

	/**
	 * @inheritDoc
	 */
	protected function getKeyPurposeMap() {
		return [
			'rank_math_title'       => self::PURPOSE_SEO_TITLE,
			'rank_math_description' => self::PURPOSE_SEO_META_DESC,
		];
	}
}
