<?php

namespace WPML\Compatibility\Divi\DynamicContent;

use WPML\Convert\Ids;
use WPML\FP\Fns;

class Hooks implements \IWPML_Frontend_Action {

	const AFTER_DIVI_PRIORITY = 20;

	public function add_hooks() {
		add_filter( 'et_builder_resolve_dynamic_content', [ $this, 'translateIds' ], self::AFTER_DIVI_PRIORITY, 6 );
	}

	/**
	 * @param string  $content
	 * @param string  $name
	 * @param array   $settings
	 * @param integer $postId
	 * @param string  $context
	 * @param array   $overrides
	 *
	 * @return string
	 */
	public function translateIds( $content, $name, $settings, $postId, $context, $overrides ) {
		$translate = Fns::withNamedLock(
			__CLASS__ . '::translateIds',
			Fns::identity(),
			function ( $content, $name, $settings, $postId, $context, $overrides ) {
				if ( isset( $settings['post_id'] ) ) {
					$settings['post_id'] = Ids::convert( $settings['post_id'], get_post_type( $settings['post_id'] ), true );
					$content             = apply_filters( 'et_builder_resolve_dynamic_content', '', $name, $settings, $postId, $context, $overrides );
				}
				return $content;
			}
		);

		return $translate( $content, $name, $settings, $postId, $context, $overrides );
	}
}
