<?php

namespace WPML\WPSEO\RankMathSEO\PrimaryCategory;

use WPML\WPSEO\Shared\PrimaryCategory\BaseHooks;

class Hooks extends BaseHooks {

	/**
	 * Get mapping of meta keys to taxonomy names.
	 *
	 * @return array
	 */
	public function getMetaKeysMapping() {
		return [
			'rank_math_primary_category'    => 'category',
			'rank_math_primary_product_cat' => 'product_cat',
		];
	}
}
