<?php

namespace WPML\ATE\Proxies;

use WPML_TM_ATE_AMS_Endpoints;

/**
 * Class ProxyInterceptorLoader
 *
 * Loads a lightweight JS "proxy interceptor" that rewrites external requests to go
 * through WPML's internal REST proxy when strict Content Security Policy (CSP)
 * rules block direct calls to third‑party domains (e.g., ATE/AMS).
 *
 *
 * Constants:
 * - PROXY_PATH: Internal REST endpoint used to proxy external requests.
 * - HANDLE_JS:  Script handle for the interceptor.
 *
 * @package WPML\ATE\Proxies
 * @see     WPML_TM_ATE_AMS_Endpoints for host discovery (ATE/AMS)
 * @see     res/js/wpml-proxy-interceptor.js for client-side logic
 */
class ProxyInterceptorLoader {

	/**
	 * Internal REST endpoint used to proxy external requests.
	 *
	 * @var string
	 */
	const PROXY_REST_PATH = '/wpml/v1/proxy';
	/**
	 * Script handle for the interceptor.
	 *
	 * @var string
	 */
	const HANDLE_JS = 'wpml-proxy-interceptor';

	/**
	 * Whether the interceptor script has already been registered/enqueued.
	 *
	 * @var bool
	 */
	private $isInitialized = false;

	/**
	 * Singleton instance
	 *
	 * @var self|null
	 */
	private static $instance = null;

	/**
	 * List of domain patterns that should be routed through the proxy.
	 * Examples: hosts for ATE, AMS, and wpml.org.
	 *
	 * @var string[]
	 */
	private $domains = [];

	/**
	 * Private constructor for singleton.
	 */
	private function __construct() {
		$this->domains = self::getAllowedDomains();
	}

	static function getAllowedDomains() {
		$ateEndpoints = new WPML_TM_ATE_AMS_Endpoints();

		return [
			$ateEndpoints->get_ATE_host(),
			$ateEndpoints->get_AMS_host(),
		];
	}

	/**
	 * Retrieve the singleton instance.
	 *
	 * @return self
	 */
	public static function get() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}

		return self::$instance;
	}

	/**
	 * Determine if the proxy mechanism should be enabled.
	 *
	 * Can be disabled by defining the constant `WPML_DISABLE_PROXY` as true.
	 *
	 * @return bool True when proxy should be active; false to bypass.
	 */
	public function shouldEnableProxy() {
		return ! defined( 'WPML_DISABLE_PROXY' ) || ! WPML_DISABLE_PROXY;
	}

	/**
	 * Enqueue a JS file so that it loads via the proxy endpoint and remains CSP‑compliant.
	 *
	 * This will ensure the interceptor is enabled and then register/enqueue the given script
	 * with a proxied URL and the interceptor script as a dependency.
	 *
	 * @param string      $handle    Unique script handle.
	 * @param string      $url       Original (external) URL to the script to be proxied.
	 * @param string[]    $deps      Additional script dependencies.
	 * @param string|bool $ver       Script version string or false for no version.
	 * @param bool        $in_footer Whether to load in footer.
	 *
	 * @return void
	 */
	public function enqueueJS( string $handle, string $url, array $deps = array(), $ver = false, $in_footer = true ) {
		if ( ! $this->isInitialized ) {
			$this->enable();
		}
		$url = $this->getProxyUrl( $url );
		$url = add_query_arg(['_wpnonce' => wp_create_nonce( 'wp_rest' )], $url);

		$deps = array_merge( $deps, [ self::HANDLE_JS ] );

		wp_register_script( $handle, $url, $deps, $ver, $in_footer );

		wp_enqueue_script( $handle );
	}

	/**
	 * Register and enqueue the proxy interceptor, exposing its configuration.
	 *
	 * Registers the dedicated JS file, exposes options (domains, proxy path, nonce)
	 * through an inline script, and enqueues it. Subsequent calls are no‑ops.
	 *
	 * @return void
	 */
	public function enable() {
		$src = plugins_url( 'res/js/wpml-proxy-interceptor.js', WPML_PLUGIN_PATH . '/sitepress.php' );
		wp_register_script( self::HANDLE_JS, $src, [], ICL_SITEPRESS_SCRIPT_VERSION, true );

		// Expose options to the inline script
		wp_add_inline_script( self::HANDLE_JS, 'window.wpmlProxyOptions = ' . wp_json_encode( [
				'domains'   => $this->domains,
				'proxyPath' => (string) $this->getProxyUrl( '' ),
				'nonce'     => wp_create_nonce( 'wp_rest' ),
			] ) . ';', 'before' );

		// Only localize options; logic lives in the dedicated JS file.
		wp_enqueue_script( self::HANDLE_JS );
		$this->isInitialized = true;
	}

	/**
	 * @param string $url
	 * @return string
	 */
	private function getProxyUrl( $url ) {
		$proxyUrl = get_rest_url( null, self::PROXY_REST_PATH );
		$proxyUrl = add_query_arg( [ 'url' => $url ], $proxyUrl );

		return $proxyUrl;
	}
}
