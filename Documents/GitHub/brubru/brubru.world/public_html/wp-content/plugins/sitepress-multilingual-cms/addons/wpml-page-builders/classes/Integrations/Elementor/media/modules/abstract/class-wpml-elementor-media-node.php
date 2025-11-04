<?php

abstract class WPML_Elementor_Media_Node {

	/** @var IWPML_PB_Media_Find_And_Translate $media_translate */
	protected $media_translate;

	public function __construct( IWPML_PB_Media_Find_And_Translate $media_translate ) {
		$this->media_translate = $media_translate;
	}

	/**
	 * @param array  $settings
	 * @param string $property
	 * @param string $lang
	 * @param string $source_lang
	 *
	 * @return mixed
	 */
	protected function translate_image_property( $settings, $property, $lang, $source_lang ) {
		if ( isset( $settings[ $property ] ) ) {
			$settings[ $property ] = $this->translate_image_array( $settings[ $property ], $lang, $source_lang );
		}

		return $settings;
	}

	/**
	 * @param array  $settings
	 * @param string $property
	 * @param string $lang
	 * @param string $source_lang
	 *
	 * @return mixed
	 */
	protected function translate_images_property( $settings, $property, $lang, $source_lang ) {
		if ( isset( $settings[ $property ] ) ) {

			foreach ( $settings[ $property ] as &$image ) {
				$image = $this->translate_image_array( $image, $lang, $source_lang );
			}
		}

		return $settings;
	}

	/**
	 * @param array  $image
	 * @param string $lang
	 * @param string $source_lang
	 *
	 * @return mixed
	 */
	public function translate_image_array( $image, $lang, $source_lang ) {
		if ( isset( $image['id'] ) && $image['id'] ) {
			$image['id'] = $this->media_translate->translate_id( $image['id'], $lang );
		}
		if ( isset( $image['url'] ) && $image['url'] ) {
			$image['url'] = $this->media_translate->translate_image_url( $image['url'], $lang, $source_lang );
		}

		return $image;
	}

	// phpcs:disable WordPress.WP.I18n.NonSingularStringLiteralText, WordPress.WP.I18n.LowLevelTranslationFunction, WordPress.WP.I18n.TooManyFunctionArgs, WordPress.WP.I18n.NonSingularStringLiteralDomain
	abstract public function translate( $settings, $target_lang, $source_lang );
}
