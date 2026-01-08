<?php

declare( strict_types=1 );

/**
 * Minimal REST proxy endpoint as a single class.
 * Route: /wp-json/wpml/v1/proxy
 */
final class WPML_Proxy {
	const TIMEOUT = 30;
	const ROUTE = '/wpml/v1/proxy';
	const BLOCKED_HEADERS
		= [
			'transfer-encoding',
			'connection',
			'keep-alive',
			'proxy-authenticate',
			'proxy-authorization',
			'te',
			'trailer',
			'upgrade',
			'content-encoding',
			'content-length',
		];


	/**
	 * Even earlier interception during plugins_loaded (priority 0).
	 * This runs before init/parse_request/REST bootstrap, reducing overall load.
	 */
	public static function maybe_handle_request() {
		// Detect both pretty permalinks and query-string style REST access.
		$rest_route = self::getRestRoute();

		if ( ! static::routeMatches( $rest_route) ) {
			return; // Not our endpoint.
		}

		$nonce = self::getWPNonce();
		if ( ! wp_verify_nonce( $nonce, 'wp_rest' ) ) {
			self::error( 401, 'invalid_wp_nonce', 'the wp nonce is invalid' );
			exit;
		}

		// Serve immediately using the same logic as parse_request interception.
		$self = new self();

		$input       = array_merge( (array) $_GET, (array) $_POST );
		$rawBody     = $self->readRawBody();
		$contentType = isset( $_SERVER['CONTENT_TYPE'] ) ? strtolower( (string) $_SERVER['CONTENT_TYPE'] ) : '';
		if ( $rawBody !== '' && strpos( $contentType, 'application/json' ) !== false ) {
			$decoded = json_decode( $rawBody, true );
			if ( is_array( $decoded ) ) {
				$input = array_merge( $input, $decoded );
			}
		}

		$method = isset( $_SERVER['REQUEST_METHOD'] ) ? (string) $_SERVER['REQUEST_METHOD'] : 'GET';
		$p      = [
			'url'          => isset( $input['url'] ) ? $input['url'] : null,
			'method'       => strtoupper( isset( $input['method'] ) ? (string) $input['method'] : $method ),
			'query'        => isset( $input['query'] ) ? $input['query'] : null,
			'headers'      => isset( $input['headers'] ) ? $input['headers'] : [],
			'body'         => array_key_exists( 'body', $input ) ? $input['body'] : null,
			'content_type' => isset( $input['content_type'] ) ? $input['content_type'] : null,
			'__raw_body'   => $rawBody,
			'__ct'         => $contentType,
		];

		if ( ! is_array( $p['headers'] ) ) {
			$p['headers'] = $p['headers'] ? [ $p['headers'] ] : [];
		}
		if ( $p['body'] === null && $p['__raw_body'] !== '' ) {
			$p['body'] = $p['__raw_body'];
		}
		if ( empty( $p['content_type'] ) && ! empty( $p['__ct'] ) ) {
			$p['content_type'] = $p['__ct'];
		}

		try {
			$self->validate( $p );
			$url     = $self->buildUrl( (string) $p['url'], $p['query'] );
			$headers = $self->parseHeaders( $p['headers'], isset( $p['content_type'] ) ? (string) $p['content_type'] : null );

			$args = [
				'method'      => (string) $p['method'],
				'headers'     => $headers,
				'timeout'     => self::TIMEOUT,
				'redirection' => 0,
			];
			if ( strtoupper( (string) $p['method'] ) !== 'GET' && $p['body'] !== null ) {
				$args['body'] = is_array( $p['body'] ) ? http_build_query( $p['body'] ) : (string) $p['body'];
			}

			$result = wp_remote_request( $url, $args );
			if ( is_wp_error( $result ) ) {
				throw new RuntimeException( $result->get_error_message() );
			}

			$status      = (int) wp_remote_retrieve_response_code( $result );
			$respHeaders = wp_remote_retrieve_headers( $result );
			if ( is_object( $respHeaders ) && method_exists( $respHeaders, 'getAll' ) ) {
				$respHeaders = $respHeaders->getAll();
			} elseif ( is_object( $respHeaders ) ) {
				$respHeaders = (array) $respHeaders;
			}
			$body        = wp_remote_retrieve_body( $result );
			$respHeaders = $self->filterHeaders( (array) $respHeaders );

			if ( function_exists( 'status_header' ) ) {
				status_header( (int) $status );
			}
			if ( function_exists( 'http_response_code' ) ) {
				@http_response_code( (int) $status );
			}
			foreach ( $respHeaders as $name => $value ) {
				if ( $name === '' ) {
					continue;
				}
				$line = $name . ': ' . ( is_array( $value ) ? implode( ', ', $value ) : (string) $value );
				@header( $line, true );
			}
			echo (string) $body; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
			exit;
		} catch ( Throwable $e ) {
			self::error( 500, 'internal_error', $e->getMessage() );
			exit;
		}
	}


	/**
	 * @return false|string|null
	 */
	public static function getRestRoute() {
		$rest_route = isset( $_GET['rest_route'] ) ? (string) $_GET['rest_route'] : null;
		if ( ! $rest_route ) {
			$uri        = isset( $_SERVER['REQUEST_URI'] ) ? (string) $_SERVER['REQUEST_URI'] : '';
			$qPos       = strpos( $uri, '?' );
			$path       = $qPos === false ? $uri : substr( $uri, 0, $qPos );
			$rest_route = $path;
		}

		return $rest_route;
	}

	/**
	 * Extract REST nonce from headers or params.
	 *
	 * @return string|null
	 */
	private static function getWPNonce() {
		if ( isset( $_SERVER['HTTP_X_WP_NONCE'] ) && $_SERVER['HTTP_X_WP_NONCE'] !== '' ) {
			return (string) $_SERVER['HTTP_X_WP_NONCE'];
		}
		if ( isset( $_GET['_wpnonce'] ) && $_GET['_wpnonce'] !== '' ) {
			return (string) $_GET['_wpnonce'];
		}
		if ( isset( $_POST['_wpnonce'] ) && $_POST['_wpnonce'] !== '' ) {
			return (string) $_POST['_wpnonce'];
		}

		return null;
	}

	private function validate( array $p ) {
		$url    = isset( $p['url'] ) ? (string) $p['url'] : '';
		$method = isset( $p['method'] ) ? strtoupper( (string) $p['method'] ) : '';
		if ( $url === '' || $method === '' ) {
			throw new InvalidArgumentException( 'Required parameters missing.' );
		}
		$parts   = parse_url( $url );
		$host    = isset( $parts['host'] ) ? strtolower( (string) $parts['host'] ) : '';
		$allowed = $this->allowedHosts();
		if ( $host === '' || ! $this->isAllowedHost( $host, $allowed ) ) {
			throw new InvalidArgumentException( 'Invalid URL. Host is not allowed.' );
		}
	}

	private function allowedHosts() {
		$hosts = \WPML\ATE\Proxies\ProxyInterceptorLoader::getAllowedDomains();
		if ( is_array( $hosts ) && ! empty( $hosts ) ) {
			return $hosts;
		}

		return [ '*.wpml.org' ];
	}

	private function isAllowedHost( string $host, array $allowed ) {
		foreach ( $allowed as $pattern ) {
			$pattern = strtolower( trim( (string) $pattern ) );
			if ( $pattern === '' ) {
				continue;
			}
			if ( strpos( $pattern, '*.' ) === 0 ) {
				$base   = substr( $pattern, 2 );
				$suffix = '.' . $base;
				if ( $host === $base || ( strlen( $host ) > strlen( $suffix ) && substr( $host, - strlen( $suffix ) ) === $suffix ) ) {
					return true;
				}
			}
			if ( $host === $pattern ) {
				return true;
			}
		}

		return false;
	}

	private function buildUrl( string $url, $query ) {
		if ( is_array( $query ) ) {
			$query = http_build_query( $query );
		}
		if ( is_string( $query ) && $query !== '' ) {
			$parts = parse_url( $url );
			if ( $parts ) {
				$base = ( $parts['scheme'] ?? '' ) !== '' ? $parts['scheme'] . '://' : '';
				$base .= $parts['host'] ?? '';
				$base .= isset( $parts['port'] ) ? ':' . $parts['port'] : '';
				$base .= $parts['path'] ?? '';

				return $base . '?' . $query;
			}
		}

		return $url;
	}

	private function parseHeaders( array $lines, $contentType ) {
		$headers = [];
		foreach ( $lines as $line ) {
			if ( ! is_string( $line ) ) {
				continue;
			}
			$pos = strpos( $line, ':' );
			if ( $pos === false ) {
				continue;
			}
			$name  = trim( substr( $line, 0, $pos ) );
			$value = trim( substr( $line, $pos + 1 ) );
			if ( $name !== '' ) {
				$headers[ $name ] = $value;
			}
		}
		if ( $contentType && ! array_key_exists( 'Content-Type', $headers ) ) {
			$headers['Content-Type'] = $contentType;
		}

		return $headers;
	}

	private function filterHeaders( array $headers ) {
		$out = [];
		foreach ( $headers as $name => $value ) {
			$ln = strtolower( (string) $name );
			if ( in_array( $ln, self::BLOCKED_HEADERS, true ) ) {
				continue;
			}
			$out[ $name ] = is_array( $value ) ? implode( ', ', $value ) : $value;
		}

		return $out;
	}

	private function readRawBody() {
		$raw = file_get_contents( 'php://input' );

		return $raw === false ? '' : $raw;
	}

	/**
	 * @return void
	 */
	public static function error( $status_code, $error, $message ) {
		if ( function_exists( 'status_header' ) ) {
			status_header( $status_code );
		}
		if ( function_exists( 'http_response_code' ) ) {
			@http_response_code( $status_code );
		}
		@header( 'Content-Type: application/json', true );
		echo json_encode( [ 'error' => $error, 'message' => $message ] );
		exit;
	}

	public static function routeMatches( $rest_route ) {
		$prefix = '/' . ltrim( (function_exists('rest_get_url_prefix') ? rest_get_url_prefix() : 'wp-json'), '/' );
		return (
			$rest_route === self::ROUTE
			|| strpos( $rest_route, $prefix . self::ROUTE ) !== false
		);
	}

}

if ( function_exists( 'add_action' ) ) {
	add_action( 'plugins_loaded', [ 'WPML_Proxy', 'maybe_handle_request' ], 0 );
}
