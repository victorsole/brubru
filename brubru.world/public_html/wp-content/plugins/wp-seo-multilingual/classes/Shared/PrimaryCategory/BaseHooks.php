<?php

namespace WPML\WPSEO\Shared\PrimaryCategory;

abstract class BaseHooks implements \IWPML_Frontend_Action, \IWPML_Backend_Action {

	/**
	 * Get mapping of meta keys to taxonomy names.
	 * To be implemented in child classes.
	 *
	 * @return array
	 */
	abstract public function getMetaKeysMapping();

	public function add_hooks() {
		add_filter( 'get_post_metadata', [ $this, 'translateTermId' ], 20, 4 );
	}

	public function remove_hooks() {
		remove_filter( 'get_post_metadata', [ $this, 'translateTermId' ], 20 );
	}

	/**
	 * Translates the primary category ID.
	 *
	 * @param null   $value
	 * @param int    $postId
	 * @param string $key
	 * @param bool   $single
	 *
	 * @return int|int[]|null
	 */
	public function translateTermId( $value, $postId, $key, $single ) {
		$metaKeysMapping = $this->getMetaKeysMapping();
		if ( in_array( $key, array_keys( $metaKeysMapping ), true ) ) {
			$this->remove_hooks();
			$value = get_post_meta( $postId, $key, true );
			$this->add_hooks();

			$args     = [
				'element_id'   => $postId,
				'element_type' => get_post_type( $postId ),
			];
			$language = apply_filters( 'wpml_element_language_code', false, $args );
			$value    = apply_filters( 'wpml_object_id', $value, $metaKeysMapping[ $key ], true, $language );

			if ( ! $single ) {
				$value = [ $value ];
			}
		}

		return $value;
	}
}
