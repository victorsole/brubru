<?php

interface IWPML_PB_Media_Find_And_Translate {

	/**
	 * @param string $url
	 * @param string $lang
	 * @param string $source_lang
	 * @param string $tag_name
	 *
	 * @return string
	 */
	public function translate_image_url( $url, $lang, $source_lang, $tag_name = '' );

	/**
	 * @param int    $id
	 * @param string $lang
	 *
	 * @return int
	 */
	public function translate_id( $id, $lang );

	public function reset_translated_ids();

	/** @return array */
	public function get_translated_ids();

	/**
	 * @return array
	 */
	public function get_used_media_in_post();
}
