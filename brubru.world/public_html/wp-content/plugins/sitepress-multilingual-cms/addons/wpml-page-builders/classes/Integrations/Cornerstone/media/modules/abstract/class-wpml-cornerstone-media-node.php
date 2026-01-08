<?php

abstract class WPML_Cornerstone_Media_Node {

	/** @var IWPML_PB_Media_Find_And_Translate $media_translate */
	protected $media_translate;

	public function __construct( IWPML_PB_Media_Find_And_Translate $media_translate ) {
		$this->media_translate = $media_translate;
	}

	/**
	 * @param array  $node_data
	 * @param string $target_lang
	 * @param string $source_lang
	 *
	 * @return array
	 *
	 * phpcs:disable WordPress.WP.I18n.NonSingularStringLiteralText, WordPress.WP.I18n.LowLevelTranslationFunction, WordPress.WP.I18n.TooManyFunctionArgs, WordPress.WP.I18n.NonSingularStringLiteralDomain
	 */
	abstract public function translate( $node_data, $target_lang, $source_lang );
}
