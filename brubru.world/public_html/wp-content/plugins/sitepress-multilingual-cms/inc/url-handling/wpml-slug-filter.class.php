<?php

/**
 * Class WPML_Slug_Filter
 *
 * @package    wpml-core
 * @subpackage url-handling
 */
class WPML_Slug_Filter extends WPML_Full_PT_API {

	/**
	 * @param wpdb                  $wpdb
	 * @param SitePress             $sitepress
	 * @param WPML_Post_Translation $post_translations
	 */
	public function __construct( &$wpdb, &$sitepress, &$post_translations ) {
		parent::__construct( $wpdb, $sitepress, $post_translations );
		add_filter( 'wp_unique_term_slug', array( $this, 'wp_unique_term_slug' ), 10, 3 );
		add_filter( 'wp_insert_term_duplicate_term_check', array( $this, 'wp_insert_term_duplicate_term_check' ), 10, 4 );

		add_filter( 'wp_unique_post_slug', array( $this, 'wp_unique_post_slug' ), 100, 6 );
	}

	/**
	 * @param string $slug
	 * @param object $term
	 * @param string $original_slug
	 *
	 * @return string
	 */
	public function wp_unique_term_slug( $slug, $term, $original_slug ): string {
		if ( $slug !== $original_slug ) {
			$lang = $this->lang_term_slug_save( $term->taxonomy );
			$slug = WPML_Terms_Translations::term_unique_slug( $original_slug, $term->taxonomy, $lang, $term->parent );
		}

		return $slug;
	}

	/**
	 * @param stdClass $duplicate_term Duplicate term row from terms table, if found.
	 * @param string   $term           Term being inserted.
	 * @param string   $taxonomy       Taxonomy name.
	 * @param array    $args           Array of arguments passed to `wp_insert_term()`.
	 *
	 * @return stdClass|null
	 */
	public function wp_insert_term_duplicate_term_check( $duplicate_term, $term, $taxonomy, $args ) {
		if ( $duplicate_term ) {

			$lang   = $this->lang_term_slug_save( $taxonomy );
			$parent = isset( $args['parent'] ) ? (int) $args['parent'] : 0;

			if ( ! WPML_Terms_Translations::term_slug_exists( $duplicate_term->slug, $taxonomy, $lang, $parent ) ) {
				$duplicate_term = null;
			}
		}

		return $duplicate_term;
	}


	private function lang_term_slug_save( $taxonomy ) {
		$active_lang_codes = array_keys( $this->sitepress->get_active_languages() );
		if ( ! in_array(
			( $lang = (string) filter_input( INPUT_POST, 'icl_tax_' . $taxonomy . '_language' ) ),
			$active_lang_codes,
			true
		)
			 && ! in_array( ( $lang = (string) filter_input( INPUT_POST, 'language' ) ), $active_lang_codes, true )
		) {
			$lang = $this->sitepress->get_current_language();
		}
		$lang = 'all' === $lang ? $this->sitepress->get_default_language() : $lang;

		return $lang;
	}

	function wp_unique_post_slug( $slug_suggested, $post_id, $post_status, $post_type, $post_parent, $slug ) {
		if ( $post_status !== 'auto-draft' && $this->sitepress->is_translated_post_type( $post_type ) ) {
			$post_language       = $post_id ? $this->post_translations->get_element_lang_code( $post_id ) : $this->sitepress->get_current_language();
			$post_language       = $post_language ?: $this->sitepress->post_translations()->get_save_post_lang( $post_id, $this->sitepress );
			$parent              = is_post_type_hierarchical( $post_type ) ? (int) $post_parent : false;
			$slug_suggested_wpml = $this->find_unique_slug_post( $post_id, $post_type, $post_language, $parent, $slug );
		}

		return isset( $slug_suggested_wpml ) ? $slug_suggested_wpml : $slug_suggested;
	}

	private function post_slug_exists( $post_id, $post_language, $slug, $post_type, $parent = false ) {
		$parent_snippet           = $parent === false ? '' : $this->wpdb->prepare( ' AND p.post_parent = %d ', $parent );
		$post_name_check_sql      = "	SELECT p.post_name
										FROM {$this->wpdb->posts} p
										JOIN {$this->wpdb->prefix}icl_translations t
											ON p.ID = t.element_id
												AND t.element_type = CONCAT('post_', p.post_type)
										WHERE p.post_name = %s
											AND p.ID != %d
											AND t.language_code = %s
											AND p.post_type = %s
											{$parent_snippet}
										LIMIT 1";
		$post_name_check_prepared = $this->wpdb->prepare( $post_name_check_sql, $slug, $post_id, $post_language, $post_type );
		$post_name_check          = $this->wpdb->get_var( $post_name_check_prepared );

		return (bool) $post_name_check;
	}

	private function find_unique_slug_post( $post_id, $post_type, $post_language, $post_parent, $slug ) {
		global $wp_rewrite;

		$feeds = is_array( $wp_rewrite->feeds ) ? $wp_rewrite->feeds : array();
		if ( $this->post_slug_exists( $post_id, $post_language, $slug, $post_type, $post_parent )
			 || in_array( $slug, $feeds, true )
			 || ( $post_parent !== false && preg_match( "@^($wp_rewrite->pagination_base)?\d+$@", $slug ) )
			 || apply_filters( 'wp_unique_post_slug_is_bad_flat_slug', false, $slug, $post_type )
		) {
			$suffix = 2;
			do {
				$alt_post_name   = _truncate_post_slug( $slug, 200 - ( strlen( (string) $suffix ) + 1 ) ) . "-$suffix";
				$suffix ++;
			} while ( $this->post_slug_exists( $post_id, $post_language, $alt_post_name, $post_type, $post_parent ) );
			$slug = $alt_post_name;
		}

		return $slug;
	}
}
