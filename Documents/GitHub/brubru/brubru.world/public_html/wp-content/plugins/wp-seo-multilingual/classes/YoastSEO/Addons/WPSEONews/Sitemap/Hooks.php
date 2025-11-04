<?php

namespace WPML\WPSEO\YoastSEO\Addons\WPSEONews\Sitemap;

use WPML\LIB\WP\Hooks as WPHooks;
use Yoast\WP\SEO\Models\Indexable;

use function WPML\FP\spreadArgs;

class Hooks implements \IWPML_Frontend_Action {

	public function add_hooks() {
		WPHooks::onFilter( 'Yoast\WP\News\publication_language', 10, 2 )
			->then( spreadArgs( [ $this, 'setPublicationLanguage' ] ) );
	}

	/**
	 * @param string    $language
	 * @param Indexable $indexable
	 */
	public function setPublicationLanguage( $language, $indexable ) {
		return apply_filters(
			'wpml_element_language_code',
			null,
			[
				'element_id'   => $indexable->object_id,
				'element_type' => $indexable->object_sub_type,
			]
		);
	}
}
