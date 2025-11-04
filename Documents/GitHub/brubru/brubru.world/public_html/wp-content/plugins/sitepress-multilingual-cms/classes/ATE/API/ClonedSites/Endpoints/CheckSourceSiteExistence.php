<?php

namespace WPML\TM\ATE\ClonedSites\Endpoints;

use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\FP\Either;

/**
 * Proxy endpoint for checking if a site is reachable
 * This endpoint allows checking HTTP sites from HTTPS pages by proxying the request through the server
 */
class CheckSourceSiteExistence implements IHandler {

	/**
	 * Checks if a site is reachable by making a server-side HTTP request
	 *
	 * @param Collection $data Collection containing 'url' parameter
	 *
	 * @return Either Either::of('exists'|'missing') or Either::left(error message)
	 */
	public function run( Collection $data ) {
		$url = $data->get( 'url', '' );

		if ( empty( $url ) ) {
			return Either::left( 'URL parameter is required' );
		}

		if ( defined( 'WPML_CHECK_SOURCE_SITE_EXISTENCE' ) ) {
			return Either::of( WPML_CHECK_SOURCE_SITE_EXISTENCE === 'STILL_EXISTS' ? 'exists' : 'missing' );
		}

		$isReachable = $this->isReachable( $url );

		return Either::of( $isReachable ? 'exists' : 'missing' );
	}

	/**
	 * Check if a site is reachable by making a GET request
	 *
	 * @param string $url URL to check
	 *
	 * @return bool True if site is reachable, false otherwise
	 */
	private function isReachable( $url ): bool {
		// Set up request arguments
		$args = [
			'method'      => 'GET',
			'timeout'     => 5,
			'redirection' => 5,
			'sslverify'   => false,
			'blocking'    => true,
		];

		// Make the request
		$response = wp_remote_request( $url, $args );

		// Check for errors
		if ( is_wp_error( $response ) ) {
			return false;
		}

		// Get the response code
		$response_code = wp_remote_retrieve_response_code( $response );

		// Return true if we got a 2xx response
		return $response_code >= 200 && $response_code < 300;
	}
}
