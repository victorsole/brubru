<?php

namespace WPML\WPSEO\RankMathSEO\Slugs;

use WPML\LIB\WP\Hooks as WpHooks;

class Hooks implements \IWPML_Action {

	const GENERAL_OPTIONS_KEY = 'rank-math-options-general';

	const FEATURES = [
		[ 'strip_category_base', 'taxonomy', 'category' ],
		[ 'wc_remove_product_base', 'post', 'product' ],
		[ 'wc_remove_category_base', 'taxonomy', 'product_cat' ],
	];

	/** @var \WPML_ST_Slug_Translation_Settings_Factory $slugTranslationSettingsFactory */
	private $slugTranslationSettingsFactory;

	/**
	 * @param \WPML_ST_Slug_Translation_Settings_Factory $slugTranslationSettingsFactory
	 */
	public function __construct( \WPML_ST_Slug_Translation_Settings_Factory $slugTranslationSettingsFactory ) {
		$this->slugTranslationSettingsFactory = $slugTranslationSettingsFactory;
	}

	public function add_hooks() {
		WpHooks::onAction( 'admin_init' )
			->then( [ $this, 'ensureStrippedBasesAreNotTranslated' ] );
	}

	public function ensureStrippedBasesAreNotTranslated() {
		$settings = (array) get_option( self::GENERAL_OPTIONS_KEY, [] );

		$isFeatureOn = function( $featureKey ) use ( $settings ) {
			return isset( $settings[ $featureKey ] ) && 'on' === $settings[ $featureKey ];
		};

		foreach ( self::FEATURES as $featureData ) {
			list( $featureKey, $type, $slug ) = $featureData;

			if ( $isFeatureOn( $featureKey ) ) {

				$slugSettings = $this->slugTranslationSettingsFactory->create( $type );

				if ( $slugSettings->is_translated( $slug ) ) {
					$slugSettings->set_type( $slug, false );
					$slugSettings->save();
				}
			}
		}
	}
}
