<?php

namespace WPML\LIB\WP;

use WPML\FP\Logic;
use WPML\FP\Str;
use function WPML\FP\pipe;

class Attachment {
	private static $cache = [];

	private static $withOutSizeRegEx = '/-\d+[Xx]\d+\./';

	/**
	 * @param string $urlWithMaybeSize
	 *
	 * @return string
	 */
	private static function removeSizeFromUrl( $urlWithMaybeSize ) {
		return Str::pregReplace( self::$withOutSizeRegEx, '.', $urlWithMaybeSize );
	}

	/**
	 * @param array $data
	 *
	 * @return string
	 */
	public static function extractSrcFromAttributes( $data ) {
		if ( ! array_key_exists( 'attributes', $data ) || ! is_array( $data['attributes'] ) || ! array_key_exists( 'src', $data['attributes'] ) ) {
			return '';
		}

		$src = $data['attributes']['src'];

		if ( ! is_string( $src ) || strlen( $src ) === 0 ) {
			return '';
		}

		return self::removeSizeFromUrl( $src );
	}

	/**
	 * @param string      $url
	 * @param string|null $urlWithoutSize
	 *
	 * @return int|null The found post ID, or null on failure.
	 */
	public static function idFromUrlCache( $url, $urlWithoutSize = null ) {
		if ( array_key_exists( $url, self::$cache ) ) {
			return self::$cache[ $url ];
		}

		if ( is_null( $urlWithoutSize ) ) {
			$urlWithoutSize = self::removeSizeFromUrl( $url );
		}

		if ( array_key_exists( $urlWithoutSize, self::$cache ) ) {
			return self::$cache[ $urlWithoutSize ];
		}

		return null;
	}

	/**
	 * @param string $url
	 *
	 * @return int|null The found post ID, or null on failure.
	 */
	public static function idFromUrl( $url ) {
		$urlWithoutSize = self::removeSizeFromUrl( $url );
		$maybeId        = self::idFromUrlCache( $url, $urlWithoutSize );

		if ( ! is_null( $maybeId ) && is_numeric( $maybeId ) ) {
			return $maybeId;
		}

		if ( $url !== $urlWithoutSize && $id = attachment_url_to_postid( $urlWithoutSize ) ) {
			self::$cache[ $url ]            = $id;
			self::$cache[ $urlWithoutSize ] = $id;
			return $id;
		}

		if ( $id = attachment_url_to_postid( $url ) ) {
			self::$cache[ $url ] = $id;
			return $id;
		}

		if ( $id = self::idByGuid( $url ) ) {
			self::$cache[ $url ] = $id;
			return $id;
		}

		if ( $url !== $urlWithoutSize && $id = self::idByGuid( $urlWithoutSize ) ) {
			self::$cache[ $url ]            = $id;
			self::$cache[ $urlWithoutSize ] = $id;
			return $id;
		}

		self::$cache[ $url ] = null;
		return null;
	}

	/**
	 * @param string $url
	 *
	 * @return int The found post ID, or 0 on failure.
	 */
	public static function idByGuid( $url ) {
		if ( array_key_exists( $url , self::$cache ) ) {
			return self::$cache[$url];
		}

		global $wpdb;

		$attachment = $wpdb->get_col( $wpdb->prepare( "SELECT ID FROM $wpdb->posts WHERE guid='%s' LIMIT 1", $url ) );

		return $attachment && count( $attachment )
			? $attachment[0]
			: 0;
	}

	public static function addToCache( $media ) {
		self::$cache = array_merge( self::$cache, $media );
	}


	public static function attachmentUrlsToPostIds( $urls ) {
		global $wpdb;

		if ( count( $urls ) === 0 ) {
			return [];
		}

		list( $pathes, $urlsToPathes, $pathesToUrls ) = self::getPathesFromUrls( $urls );

		$results = $wpdb->get_results(
			"SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file' AND meta_value IN (" . wpml_prepare_in( $pathes, '%s' ) . ")"
		);

		$results = array_map(
			function ( $result ) {
				return [
					'id'    => $result->post_id,
					'value' => $result->meta_value
				];
			},
			$results
		);

		return self::mapUrlsToPostIds( $results, $urls, $pathes, $urlsToPathes, $pathesToUrls );
	}

	/**
	 * @param array $urls
	 *
	 * @return array
	 */
	public static function getPathesFromUrls( $urls ) {
		$urlsToPathes = [];
		$pathesToUrls = [];
		$pathes       = [];
		foreach ( $urls as $url ) {
			$path                  = self::urlToPath( $url );
			$pathes[]              = $path;
			$urlsToPathes[ $url ]  = $path;
			$pathesToUrls[ $path ] = $url;
		}

		return [ $pathes, $urlsToPathes, $pathesToUrls ];
	}

	public static function mapUrlsToPostIds( $results, $urls, $pathes, $urlsToPathes, $pathesToUrls ) {
		$urlsToPostIds = [];
		foreach ( $urls as $url ) {
			$urlsToPostIds[ $url ] = null;
		}

		foreach ( $results as $result ) {
			foreach ( $pathes as $path ) {
				if ( $path === $result['value'] ) {
					$url                   = $pathesToUrls[ $path ];
					$urlsToPostIds[ $url ] = (int) $result['id'];
					break;
				}
			}
		}

		foreach ( $urlsToPostIds as $url => $postId ) {
			if ( ! is_null( $postId ) ) {
				continue;
			}

			$path = strtolower( $urlsToPathes[ $url ] );
			foreach ( $results as $result ) {
				if ( $path === strtolower( $result['value'] ) ) {
					$urlsToPostIds[ $url ] = (int) $result['id'];
					break;
				}
			}
		}

		return $urlsToPostIds;
	}

	/**
	 * @param string $url
	 *
	 * @return string
	 */
	public static function urlToPath( $url ) {
		$dir  = wp_get_upload_dir();
		$path = $url;

		$site_url   = parse_url( $dir['url'] );
		$image_path = parse_url( $path );

		if ( isset( $image_path['scheme'] ) && ( $image_path['scheme'] !== $site_url['scheme'] ) ) {
			$path = str_replace( $image_path['scheme'], $site_url['scheme'], $path );
		}

		if ( Str::startsWith( $dir['baseurl'] . '/', $path ) ) {
			$path = substr( $path, strlen( $dir['baseurl'] . '/' ) );
		}

		return $path;
	}
}
