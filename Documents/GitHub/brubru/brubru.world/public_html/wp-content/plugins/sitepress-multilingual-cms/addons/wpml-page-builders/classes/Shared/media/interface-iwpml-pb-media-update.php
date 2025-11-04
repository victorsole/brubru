<?php

// phpcs:disable WordPress.WP.I18n.NonSingularStringLiteralText, WordPress.WP.I18n.LowLevelTranslationFunction
interface IWPML_PB_Media_Update {

	/**
	 * @param WP_Post $post
	 */
	public function translate( $post );

	/**
	 * @param WP_Post $post
	 */
	public function find_media( $post );

	/**
	 * @return array
	 */
	public function get_media();
}
