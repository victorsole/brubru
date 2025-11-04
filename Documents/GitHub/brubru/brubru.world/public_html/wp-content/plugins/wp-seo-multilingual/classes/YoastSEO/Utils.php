<?php

namespace WPML\WPSEO\YoastSEO;

class Utils {

	const KEY_META_TITLE = 'wpseo_title';
	const KEY_META_DESC  = 'wpseo_desc';

	/**
	 * List of deprecated Yoast hooks.
	 *
	 * @var array
	 */
	private static $deprecated_hooks = [
		'wpseo_premium_post_redirect_slug_change' => [
			'since'    => '12.9.0',
			'new_name' => 'Yoast\WP\SEO\post_redirect_slug_change',
		],
	];

	/**
	 * Adds a filter considering deprecated hooks, for backward compatibility.
	 *
	 * @param string   $name      The name of the filter.
	 * @param callable $callback  The callback function we will call.
	 * @param int      $priority  The filter priority.
	 * @param int      $arguments The number of arguments.
	 */
	public static function add_filter( $name, $callback, $priority = 10, $arguments = 1 ) {
		if ( isset( self::$deprecated_hooks[ $name ] ) ) {
			if ( version_compare( constant( 'WPSEO_VERSION' ), self::$deprecated_hooks[ $name ]['since'], '>=' ) ) {
				$name = self::$deprecated_hooks[ $name ]['new_name'];
			}
		}

		add_filter( $name, $callback, $priority, $arguments );
	}

	/**
	 * Checks if we are using the premium version.
	 */
	public static function isPremium() {
		if ( ! function_exists( 'is_plugin_active' ) ) {
			require_once ABSPATH . 'wp-admin/includes/plugin.php';
		}

		return is_plugin_active( 'wordpress-seo-premium/wp-seo-premium.php' );
	}

	/**
	 * @return bool
	 */
	public static function isFrontPageWithPosts() {
		return is_front_page() && 'posts' === get_option( 'show_on_front' );
	}

	/**
	 * Checks if a post is indexable (not set to noindex).
	 *
	 * @param int|null $postId
	 *
	 * @return bool
	 */
	public static function isIndexablePost( $postId ) {
		return $postId && (int) \WPSEO_Meta::get_value( 'meta-robots-noindex', $postId ) !== 1;
	}

	/**
	 * Checks if a term is indexable (not set to noindex).
	 *
	 * @param \WP_Term $term
	 *
	 * @return bool
	 */
	public static function isIndexableTerm( $term ) {
		return (int) \WPSEO_Taxonomy_Meta::get_term_meta( $term, $term->taxonomy, 'noindex' ) !== 1;
	}
}
