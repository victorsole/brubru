<?php

namespace WPML\WPSEO\YoastSEO\PrimaryCategory;

use WPML\WPSEO\Shared\PrimaryCategory\BaseHooks;

class Hooks extends BaseHooks {

	/**
	 * Get mapping of meta keys to taxonomy names.
	 *
	 * @return array
	 */
	public function getMetaKeysMapping() {
		return [
			'_yoast_wpseo_primary_category'    => 'category',
			'_yoast_wpseo_primary_product_cat' => 'product_cat',
		];
	}
}
