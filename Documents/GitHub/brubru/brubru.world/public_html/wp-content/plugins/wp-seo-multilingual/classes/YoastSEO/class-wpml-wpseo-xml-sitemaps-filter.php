<?php

use WPML\WPSEO\YoastSEO\Utils;
use WPML\Settings\LanguageNegotiation;

class WPML_WPSEO_XML_Sitemaps_Filter implements IWPML_Action {

	/**
	 * @var SitePress
	 */
	protected $sitepress;

	/**
	 * @var WPML_URL_Converter
	 */
	private $wpml_url_converter;

	/**
	 * @var WPML_Debug_BackTrace
	 */
	private $back_trace;

	/**
	 * @var WPSEO_Sitemap_Image_Parser
	 */
	private $image_parser;

	/**
	 * @param SitePress                  $sitepress
	 * @param WPML_URL_Converter         $wpml_url_converter
	 * @param WPSEO_Sitemap_Image_Parser $image_parser
	 * @param WPML_Debug_BackTrace       $back_trace
	 */
	public function __construct( $sitepress, $wpml_url_converter, WPSEO_Sitemap_Image_Parser $image_parser, WPML_Debug_BackTrace $back_trace = null ) {
		$this->sitepress          = $sitepress;
		$this->wpml_url_converter = $wpml_url_converter;
		$this->image_parser       = $image_parser;
		$this->back_trace         = $back_trace;
	}

	public function add_hooks() {
		if ( $this->isSitemapRequest() ) {
			$this->add_sitemap_hooks();
		}
	}

	private function isSitemapRequest(): bool {
		if ( ! isset( $_SERVER['REQUEST_URI'] ) ) {
			return false;
		}

		$request_uri = sanitize_text_field( wp_unslash( $_SERVER['REQUEST_URI'] ) );
		$path        = (string) parse_url( $request_uri, PHP_URL_PATH );
		$extension   = pathinfo( $path, PATHINFO_EXTENSION );

		if ( stripos( $request_uri, 'sitemap' ) !== false && in_array( $extension, [ 'xml', 'xsl' ], true ) ) {
			return true;
		}

		return false;
	}
	private function add_sitemap_hooks() {
		global $wpml_query_filter;

		if ( LanguageNegotiation::isDomain() ) {
			add_filter( 'wpml_get_home_url', [ $this, 'get_home_url_filter' ], 10, 4 );
			add_filter( 'wpseo_posts_join', [ $wpml_query_filter, 'filter_single_type_join' ], 10, 2 );
			add_filter( 'wpseo_posts_where', [ $wpml_query_filter, 'filter_single_type_where' ], 10, 2 );
			add_filter( 'wpseo_typecount_join', [ $wpml_query_filter, 'filter_single_type_join' ], 10, 2 );
			add_filter( 'wpseo_typecount_where', [ $wpml_query_filter, 'filter_single_type_where' ], 10, 2 );
			add_action( 'wpseo_xmlsitemaps_config', [ $this, 'list_domains' ] );
		} else {
			add_filter( 'wpseo_sitemap_post_type_first_links', [ $this, 'addTranslatedFirstLinks' ], 10, 2 );
			add_filter( 'wpseo_xml_sitemap_post_url', [ $this, 'exclude_hidden_language_posts' ], 10, 2 );
			add_action( 'parse_query', [ $this, 'remove_sitemap_from_non_default_languages' ] );
		}

		if ( LanguageNegotiation::isDir() ) {
			add_filter( 'wpml_get_home_url', [ $this, 'maybe_return_original_url_in_get_home_url_filter' ], 10, 2 );
		}

		add_filter( 'wpseo_build_sitemap_post_type', [ $this, 'wpseo_build_sitemap_post_type_filter' ] );
		add_filter( 'wpseo_exclude_from_sitemap_by_post_ids', [ $this, 'exclude_translations_of_static_pages' ] );
		add_filter( 'wpseo_exclude_from_sitemap_by_term_ids', [ $this, 'excludeHiddenLanguagesTerms' ] );
	}

	/**
	 * @param array  $links
	 * @param string $postType
	 *
	 * @return array
	 */
	public function addTranslatedFirstLinks( $links, $postType ) {
		if ( ! $this->sitepress->is_translated_post_type( $postType ) ) {
			return $links;
		}

		$defaultLang = $this->sitepress->get_default_language();
		$activeLangs = $this->sitepress->get_active_languages();
		unset( $activeLangs[ $defaultLang ] );

		$hasPageOnFront = (bool) $this->get_post_id_for_option( 'page_on_front', $defaultLang );
		foreach ( $activeLangs as $langCode => $langData ) {
			$url     = null;
			$lastmod = null;
			$images  = null;

			switch ( $postType ) {
				case 'page':
					$postId = $this->get_post_id_for_option( 'page_on_front', $langCode );
					if ( ! $hasPageOnFront || Utils::isIndexablePost( $postId ) ) {
						$url = $this->get_translated_home_url( $langCode );
						if ( 'page' === get_option( 'show_on_front' ) ) {
							$lastmod = get_the_modified_time( 'c', $postId );
						}
						$images = $this->get_images( $postId );
					}
					break;
				case 'post':
					$postId = $this->get_post_id_for_option( 'page_for_posts', $langCode );
					if ( Utils::isIndexablePost( $postId ) ) {
						$url = get_permalink( $postId );
					}
					break;
				case 'product':
					if ( defined( 'WC_PLUGIN_FILE' ) ) {
						$postId = $this->get_post_id_for_option( 'woocommerce_shop_page_id', $langCode );
						if ( Utils::isIndexablePost( $postId ) ) {
							$url = get_permalink( $postId );
						}
						break;
					}
					// If we don't have WooCommerce, we fall through to the default case.
				default:
					$this->sitepress->switch_lang( $langCode );
					$url = get_post_type_archive_link( $postType );
					$this->sitepress->switch_lang();
			}

			if ( $url ) {
				$link = [
					'loc' => $url,
					'mod' => $lastmod ?? WPSEO_Sitemaps::get_last_modified_gmt( $postType ),
					'chf' => 'daily',
					'pri' => 1,
				];
				if ( $images ) {
					$link['images'] = $images;
				}
				$links[] = $link;
			}
		}

		return $links;
	}


	/**
	 * Update home_url for language per-domain configuration to return correct URL in sitemap.
	 *
	 * @param string $home_url
	 * @param string $url
	 * @param string $path
	 * @param string $orig_scheme
	 *
	 * @return bool|mixed|string
	 */
	public function get_home_url_filter( $home_url, $url, $path, $orig_scheme ) {
		if ( 'relative' !== $orig_scheme ) {
			$home_url = $this->wpml_url_converter->convert_url( $home_url, $this->sitepress->get_current_language() );
		}
		return $home_url;
	}

	/**
	 * List sitemaps in other domains.
	 * Only used when language URL format is 'one domain per language'.
	 */
	public function list_domains() {
		$ls_languages = $this->sitepress->get_ls_languages();
		if ( $ls_languages ) {

			echo '<h3>' . esc_html__( 'WPML', 'wp-seo-multilingual' ) . '</h3>';
			echo esc_html__( 'Sitemaps for each language can be accessed below. You need to submit all these sitemaps to Google.', 'wp-seo-multilingual' );
			echo '<table class="wpml-sitemap-translations" style="margin-left: 1em; margin-top: 1em;">';

			foreach ( $ls_languages as $lang ) {
				$url = $lang['url'] . 'sitemap_index.xml';
				echo '<tr>';
				echo '<td>';
				echo '<a ';
				echo 'href="' . esc_url( $url ) . '" ';
				echo 'target="_blank" ';
				echo 'class="button-secondary" ';
				printf(
					"style=\"background-image:url('%s'); background-repeat: no-repeat; background-position: 2px center; background-size: 16px; padding-left: 20px; width: 100%%;\"",
					esc_url( $lang['country_flag_url'] )
				);
				echo '>';
				echo esc_html( $lang['translated_name'] );
				echo '</a>';
				echo '</td>';
				echo '</tr>';
			}
			echo '</table>';
		}
	}

	/**
	 * Deactivate auto-adjust-ids while building the sitemap.
	 *
	 * @param string $type
	 * @return string
	 */
	public function wpseo_build_sitemap_post_type_filter( $type ) {
		global $sitepress_settings;
		// Before building the sitemap and as we are on front-end make sure links aren't translated.
		// The setting should not be updated in DB.
		$sitepress_settings['auto_adjust_ids'] = 0;

		if ( ! LanguageNegotiation::isDomain() ) {
			remove_filter( 'terms_clauses', [ $this->sitepress, 'terms_clauses' ] );
		}

		remove_filter( 'category_link', [ $this->sitepress, 'category_link_adjust_id' ], 1 );

		return $type;
	}

	/**
	 * Exclude posts under hidden language.
	 *
	 * @param  string   $url  Post URL.
	 * @param  stdClass $post Object with some post information.
	 *
	 * @return string|null
	 */
	public function exclude_hidden_language_posts( $url, $post ) {
		// Check that at least ID is set in post object.
		if ( ! isset( $post->ID ) ) {
			return $url;
		}

		// Get list of hidden languages.
		$hidden_languages = $this->sitepress->get_setting( 'hidden_languages', [] );

		// If there are no hidden languages return original URL.
		if ( empty( $hidden_languages ) ) {
			return $url;
		}

		// Get language information for post.
		$language_info = $this->sitepress->post_translations()->get_element_lang_code( $post->ID );

		// If language code is one of the hidden languages return null to skip the post.
		if ( in_array( $language_info, $hidden_languages, true ) ) {
			return null;
		}

		return $url;
	}

	public function excludeHiddenLanguagesTerms( $termIds ) {
		global $wpdb;
		$hiddenLanguages = $this->sitepress->get_setting( 'hidden_languages', [] );

		if ( empty( $hiddenLanguages ) ) {
			return $termIds;
		}

		foreach ( $hiddenLanguages as $language ) {
			// phpcs:disable
			$query = $wpdb->prepare(
				"SELECT wptt.term_id
				FROM {$wpdb->prefix}term_taxonomy AS wptt
				JOIN {$wpdb->prefix}icl_translations AS iclt
					ON iclt.element_id = wptt.term_taxonomy_id
				WHERE language_code=%s AND element_type like 'tax_%'",
				$language
			);
			$terms   = $wpdb->get_col( $query );
			// phpcs:enable

			$termIds = array_merge( $termIds, array_map( 'intval', $terms ) );
		}

		return $termIds;
	}

	/**
	 * @param array $excluded_post_ids
	 *
	 * @return array
	 */
	public function exclude_translations_of_static_pages( $excluded_post_ids ) {
		$static_pages = [ 'page_on_front', 'page_for_posts' ];
		foreach ( $static_pages as $static_page ) {
			$page_id = (int) get_option( $static_page );
			if ( $page_id ) {
				$translations = (array) $this->sitepress->post_translations()->get_element_translations( $page_id );
				unset( $translations[ $this->sitepress->get_default_language() ] );
				$excluded_post_ids = array_merge( $excluded_post_ids, array_values( $translations ) );
			}
		}

		return $excluded_post_ids;
	}

	/**
	 * @param string $home_url
	 * @param string $original_url
	 *
	 * @return string
	 */
	public function maybe_return_original_url_in_get_home_url_filter( $home_url, $original_url ) {
		if ( $home_url === $original_url ) {
			return $home_url;
		}

		$places = [
			[ 'WPSEO_Post_Type_Sitemap_Provider', 'get_home_url' ],
			[ 'WPSEO_Post_Type_Sitemap_Provider', 'get_parsed_home_url' ],
			[ 'WPSEO_Post_Type_Sitemap_Provider', 'get_classifier' ],
			[ 'WPSEO_Sitemaps_Router', 'get_base_url' ],
			[ 'WPSEO_Sitemaps_Renderer', '__construct' ],
		];

		foreach ( $places as $place ) {
			if ( $this->get_back_trace()->is_class_function_in_call_stack( $place[0], $place[1] ) ) {
				return $original_url;
			}
		}

		return $home_url;
	}

	/**
	 * @return WPML_Debug_BackTrace
	 */
	private function get_back_trace() {
		if ( null === $this->back_trace ) {
			$this->back_trace = new WPML_Debug_BackTrace( phpversion() );
		}

		return $this->back_trace;
	}

	/**
	 * Get the translated post_id for a certain optionb.
	 *
	 * @param string $option The option we need.
	 * @param string $lang   The language we need.
	 * @return int
	 */
	private function get_post_id_for_option( $option, $lang ) {
		return $this->sitepress->get_object_id( get_option( $option ), 'page', false, $lang );
	}

	/**
	 * @param string $lang_code
	 *
	 * @return bool|mixed|string
	 */
	private function get_translated_home_url( $lang_code ) {
		return $this->wpml_url_converter->convert_url( home_url(), $lang_code );
	}

	/**
	 * Get a list of images attached to this page.
	 *
	 * @param int $page_id
	 * @return array
	 */
	private function get_images( $page_id ) {
		$images = [];

		if ( apply_filters( 'wpseo_xml_sitemap_include_images', true ) ) {
			$images = $this->image_parser->get_images( get_post( $page_id ) );
		}

		return $images;
	}

	/**
	 * Removes the sitemap query_var on non-default languages.
	 * This will only run when the language URL format is not per domain.
	 *
	 * @param WP_Query $wp_query Passed WP query object.
	 */
	public function remove_sitemap_from_non_default_languages( &$wp_query ) {
		if (
				$wp_query->get( 'sitemap' )
				&& $this->sitepress->get_current_language() !== $this->sitepress->get_default_language()
			) {
			unset( $wp_query->query_vars['sitemap'] );
			$wp_query->set_404();
			status_header( 404 );
		}
	}
}
