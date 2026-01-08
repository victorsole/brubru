<?php

namespace WPML\Infrastructure\WordPress\SharedKernel\Server\Application;

use WPML\Core\SharedKernel\Component\Server\Domain\CacheInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\RestApiStatusInterface;

/**
 * WordPress implementation of the REST API service interface.
 * This class contains all WordPress-specific code for checking REST API
 * functionality.
 */
class WordPressRestApiStatus implements RestApiStatusInterface
{

  /**
   * @var CacheInterface $cache
   */
    private $cache;

    const CACHE_KEY = 'wpml_rest_api_status';
    const CACHE_TTL = 300;


  public function __construct( CacheInterface $cache ) {
      $this->cache = $cache;
  }


  public function isEnabled( bool $useCache = false ): bool {
    if ( $useCache ) {
        $cached = $this->cache->get( self::CACHE_KEY );
      if ( is_bool( $cached ) ) {
        return $cached;
      }
    }

      $result = $this->checkRestApiAvailability();
      $this->cache->set( self::CACHE_KEY, $result, self::CACHE_TTL );

      return $result;
  }


  /**
   * Tests if a REST API endpoint is accessible and returns valid data
   *
   * @param string $endpoint The endpoint URL to test
   *
   * @return bool True if the endpoint is accessible and returns valid data
   */
  private function testEndpoint( string $endpoint ): bool {
      $args = [
      'timeout'     => 20,
      'redirection' => 5,
      'sslverify'   => false,
      'headers'     => [
      'Accept' => 'application/json',
      ],
      'cookies'     => $this->getCookiesWithoutSessionId(),
      ];

      // Add basic authentication if present
      if ( isset( $_SERVER['PHP_AUTH_USER'] )
       && isset( $_SERVER['PHP_AUTH_PW'] )
      ) {
          $args['headers']['Authorization'] = 'Basic '
                                        . base64_encode(
                                          $_SERVER['PHP_AUTH_USER']
                                            . ':'
                                            . $_SERVER['PHP_AUTH_PW']
                                        );
      }

      // Add a cache buster to avoid any caching issues
      $endpoint = add_query_arg( 'cachebuster', time(), $endpoint );

      $response = wp_remote_get( $endpoint, $args );

      // Check for WP error
      if ( is_wp_error( $response ) ) {
          return false;
      }

      // Check status code
      $status_code = wp_remote_retrieve_response_code( $response );
      if ( $status_code >= 400 ) {
          return false;
      }

      // Check response body is valid JSON
      $body = wp_remote_retrieve_body( $response );
      if ( empty( $body ) ) {
          return false;
      }
      $data = json_decode( $body, true );

      if ( empty( $data ) || ! is_array( $data ) ) {
          return false;
      }

      // Verify response has typical REST API structure
      return isset( $data['routes'] ) || isset( $data['namespaces'] );
  }


  /**
   * Get cookies without session ID for REST API requests
   *
   * @return array<string,string>
   */
  private function getCookiesWithoutSessionId() {
      return array_diff_key( $_COOKIE, [ 'PHPSESSID' => '' ] );
  }


  public function getEndpoint(): string {
      return get_rest_url();
  }


  /**
   * Checks if the REST API is available and functional
   *
   * @return bool True if REST API is available and working
   */
  private function checkRestApiAvailability(): bool {
    // 1) Is the REST server class even available?
    if ( ! class_exists( 'WP_REST_Server' ) ) {
        return false;
    }

      // 2) Has someone explicitly disabled the REST API?
      /** @var bool $rest_enabled */
      $rest_enabled = apply_filters( 'rest_enabled', true );
    if ( ! $rest_enabled ) {
        return false;
    }

      // 3) Are there any routes registered?
      $server = rest_get_server();
      $routes = $server->get_routes();

    if ( empty( $routes ) ) {
        return false;
    }

      $result = $this->testEndpoint( $this->getEndpoint() );
    if ( ! $result ) {
      //try again to avoid false positives warning
        $result = $this->testEndpoint( $this->getEndpoint() );
    }

      return $result;
  }


}
