<?php

// phpcs:disable WordPress.WP.I18n.NonSingularStringLiteralText, WordPress.WP.I18n.TooManyFunctionArgs, WordPress.WP.I18n.NonSingularStringLiteralDomain, WordPress.WP.I18n.LowLevelTranslationFunction
interface IWPML_PB_Media_Nodes_Iterator {

	public function translate( $data, $lang, $source_lang );

	/**
	 * @return array
	 */
	public function get_media();
}
