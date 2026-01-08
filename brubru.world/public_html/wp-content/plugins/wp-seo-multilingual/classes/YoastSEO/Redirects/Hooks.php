<?php

namespace WPML\WPSEO\YoastSEO\Redirects;

use WPML\Settings\LanguageNegotiation;

class Hooks implements \IWPML_Backend_Action {

	/** @see `WPSEO_Redirect_Ajax::set_hooks` */
	const AJAX_ADD_REDIRECT_PRIORITY    = 10;
	const AJAX_UPDATE_REDIRECT_PRIORITY = 10;

	/** @see `WPSEO_Post_Watcher::detect_slug_change` */
	const DETECT_SLUG_CHANGE_PRIORITY = 12;

	public function add_hooks() {
		if ( LanguageNegotiation::isDir() ) {
			$this->loadFiltersOn( 'wp_ajax_wpseo_add_redirect_plain', self::AJAX_ADD_REDIRECT_PRIORITY );
			$this->loadFiltersOn( 'wp_ajax_wpseo_add_redirect_regex', self::AJAX_ADD_REDIRECT_PRIORITY );
			$this->loadFiltersOn( 'wp_ajax_wpseo_update_redirect_plain', self::AJAX_UPDATE_REDIRECT_PRIORITY );
			$this->loadFiltersOn( 'wp_ajax_wpseo_update_redirect_regex', self::AJAX_UPDATE_REDIRECT_PRIORITY );
			$this->loadFiltersOn( 'post_updated', self::DETECT_SLUG_CHANGE_PRIORITY );
		}
	}

	/**
	 * @param string $hook
	 * @param int    $priority
	 */
	private function loadFiltersOn( $hook, $priority ) {
		add_action( $hook, [ $this, 'disableHomeUrlFilter' ], $priority - 1 );
		add_action( $hook, [ $this, 'restoreHomeUrlFilter' ], $priority + 1 );
	}

	public function disableHomeUrlFilter() {
		add_filter( 'wpml_get_home_url', [ $this, 'overwriteHomeUrl' ], 10, 2 );
	}

	public function restoreHomeUrlFilter() {
		remove_filter( 'wpml_get_home_url', [ $this, 'overwriteHomeUrl' ], 10 );
	}

	/**
	 * @param string $homeUrl
	 * @param string $url
	 *
	 * @return string
	 */
	public function overwriteHomeUrl( $homeUrl, $url ) {
		return $url;
	}
}
