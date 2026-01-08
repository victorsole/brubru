<?php

class WPML_Page_Builders_Media_Find_Usage implements IWPML_PB_Media_Find_And_Translate {

	/** @var array $translated_urls */
	protected $translated_urls = array();

	/** @var array $translated_ids */
	private $translated_ids = array();

	/**
	 * @return array
	 */
	public function get_used_media_in_post() {
		$media_data = [];

		foreach ( $this->translated_ids as $id ) {
			$media_data[] = [
				'id'        => $id,
				'url'       => null,
				'shortcode' => null,
			];
		}
		foreach ( $this->translated_urls as $data ) {
			$media_data[] = [
				'id'        => null,
				'url'       => $data[0],
				'shortcode' => $data[1],
			];
		}

		return $media_data;
	}

	/**
	 * @param string $url
	 * @param string $lang
	 * @param string $source_lang
	 * @param string $tag_name
	 *
	 * @return string
	 */
	public function translate_image_url( $url, $lang, $source_lang, $tag_name = '' ) {
		foreach ( $this->translated_urls as $translated_url ) {
			if ( $translated_url[0] === $url && $translated_url[1] === $tag_name ) {
				return $url;
			}
		}

		$this->translated_urls[] = [ $url, $tag_name ];

		return $url;
	}

	/**
	 * @param int    $id
	 * @param string $lang
	 *
	 * @return int
	 */
	public function translate_id( $id, $lang ) {
		if ( (int) $id < 1 ) {
			return $id;
		}

		$this->add_translated_id( $id );
		return $id;
	}

	/** @param int $id */
	private function add_translated_id( $id ) {
		if ( ! in_array( $id, $this->translated_ids, true ) ) {
			$this->translated_ids[] = $id;
		}
	}

	public function reset_translated_ids() {
		$this->translated_ids = array();
	}

	/** @return array */
	public function get_translated_ids() {
		return $this->translated_ids;
	}
}
