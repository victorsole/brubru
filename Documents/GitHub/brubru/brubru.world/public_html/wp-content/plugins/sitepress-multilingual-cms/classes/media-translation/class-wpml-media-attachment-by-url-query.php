<?php
// phpcs:disable WordPress.WP.PreparedSQL.NotPrepared
// Safe to ignore.
namespace WPML\Media\Classes;

use WPML\FP\Obj;
use WPML\FP\Str;

class WPML_Media_Attachment_By_URL_Query {
	/**
	 * @var wpdb
	 */
	private $wpdb;

	/**
	 * @var boolean Used in tests
	 */
	private $was_last_fetch_from_cache = false;

	/**
	 * \WPML\Media\Classes\WPML_Media_Attachment_By_URL_Query constructor.
	 *
	 * @param \wpdb $wpdb
	 */
	public function __construct( \wpdb $wpdb ) {
		$this->wpdb = $wpdb;
	}

	/**
	 * @return boolean
	 */
	public function getWasLastFetchFromCache() {
		return $this->was_last_fetch_from_cache;
	}

	/**
	 * @param array $source_items
	 *
	 * @return array
	 */
	private function filterItems( $source_items ) {
		return array_values( array_filter( array_unique( $source_items ) ) );
	}

	/**
	 * @param string $language
	 * @param array  $items
	 * @param string $cache_prop
	 */
	private function populateNotFoundItemsInCache( $language, $items, $cache_prop = 'id_from_guid_cache' ) {
		foreach ( $items as $item ) {
			$index = md5( $language . $item );
			if ( WPML_Media_Attachments_Query_Cache::hasCacheItem( $cache_prop, $index ) ) {
				continue;
			}
			WPML_Media_Attachments_Query_Cache::setCacheItem( $cache_prop, $index, null );
		}
	}

	/**
	 * @param array $languages
	 * @param array $urls
	 */
	public function prefetchAllIdsFromGuids( $languages, $urls ) {
		$urls = $this->filterItems( $urls );

		$cache_languages = apply_filters( 'wpml_prefetch_languages_for_mt_attachments', $languages );

		if ( ! empty( $cache_languages ) ) {
			$languages = $cache_languages;
		}

		list( $urls_with_ext, $urls_without_ext ) = $this->partItemsWithExtAndWithout( $urls );
		$urls                                     = $urls_with_ext;

		foreach ( $languages as $language ) {
			$urls = array_filter(
				$urls, function( $url ) use ( $language ) {
					$index = md5( $language . $url );
					return ! WPML_Media_Attachments_Query_Cache::hasCacheItem( 'id_from_guid_cache', $index );
				}
			);
			$this->populateNotFoundItemsInCache( $language, $urls_without_ext, 'id_from_guid_cache' );
		}

		if ( 0 === count( $urls ) ) {
			return;
		}

		$sql = "SELECT p.ID AS post_id, p.guid, t.language_code 
        FROM {$this->wpdb->posts} p 
        JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.ID 
        WHERE t.element_type = %s 
        AND t.language_code IN (" . wpml_prepare_in( $languages ) . ') 
        AND p.guid IN (' . wpml_prepare_in( $urls ) . ')';

		$results = $this->wpdb->get_results( $this->wpdb->prepare( $sql, 'post_attachment' ), ARRAY_A );
		foreach ( $results as $result ) {
			$index = md5( $result['language_code'] . $result['guid'] );
			WPML_Media_Attachments_Query_Cache::setCacheItem( 'id_from_guid_cache', $index, $result );
		}

		// We should put not found values into the cache too, otherwise they will be still queried later.
		foreach ( $languages as $language ) {
			$this->populateNotFoundItemsInCache( $language, $urls, 'id_from_guid_cache' );
		}
	}

	/**
	 * @param string $language
	 * @param string $url
	 */
	public function getIdFromGuid( $language, $url ) {
		$this->was_last_fetch_from_cache = false;
		$index                           = md5( $language . $url );

		if ( WPML_Media_Attachments_Query_Cache::hasCacheItem( 'id_from_guid_cache', $index ) ) {
			$this->was_last_fetch_from_cache = true;
			$cache_item                      = WPML_Media_Attachments_Query_Cache::getCacheItem( 'id_from_guid_cache', $index );
			return $cache_item ? $cache_item['post_id'] : null;
		}

		$sql = $this->wpdb->prepare(
			"SELECT ID FROM {$this->wpdb->posts} p
			JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.ID
			WHERE t.element_type = %s AND t.language_code = %s AND p.guid = %s",
			'post_attachment',
			$language,
			$url
		);

		$attachment_id = $this->wpdb->get_var( $sql );

		return $attachment_id;
	}

	/**
	 * @param array $languages
	 * @param array $paths
	 */
	public function prefetchAllIdsFromMetas( $languages, $paths ) {
		$paths = $this->filterItems( $paths );

		$cache_languages = apply_filters( 'wpml_prefetch_languages_for_mt_attachments', $languages );

		if ( ! empty( $cache_languages ) ) {
			$languages = $cache_languages;
		}

		list( $paths_with_ext, $paths_without_ext ) = $this->partItemsWithExtAndWithout( $paths );
		$paths                                      = $paths_with_ext;

		foreach ( $languages as $language ) {
			$paths = array_filter(
				$paths, function( $path ) use ( $language ) {
					$index = md5( $language . $path );
					return ! WPML_Media_Attachments_Query_Cache::hasCacheItem( 'id_from_meta_cache', $index );
				}
			);
			$this->populateNotFoundItemsInCache( $language, $paths_without_ext, 'id_from_meta_cache' );
		}

		if ( 0 === count( $paths ) ) {
			return;
		}

		$sql = "SELECT p.post_id, t.language_code, p.meta_value 
            FROM {$this->wpdb->postmeta} p 
            JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.post_id 
            WHERE p.meta_key = %s 
            AND t.element_type = %s
            AND t.language_code IN (" . wpml_prepare_in( $languages ) . ') 
            AND p.meta_value IN (' . wpml_prepare_in( $paths ) . ')';

		$results = $this->wpdb->get_results( $this->wpdb->prepare( $sql, '_wp_attached_file', 'post_attachment' ), ARRAY_A );

		foreach ( $results as $result ) {
			$index = md5( $result['language_code'] . $result['meta_value'] );
			WPML_Media_Attachments_Query_Cache::setCacheItem( 'id_from_meta_cache', $index, $result );
		}

		// We should put not found values into the cache too, otherwise they will be still queried later.
		foreach ( $languages as $language ) {
			$this->populateNotFoundItemsInCache( $language, $paths, 'id_from_meta_cache' );
		}
	}

	/**
	 * @param string $relative_path
	 * @param string $language
	 * @return mixed
	 */
	public function getIdFromMeta( $relative_path, $language ) {
		$this->was_last_fetch_from_cache = false;
		$index                           = md5( $language . $relative_path );

		if ( WPML_Media_Attachments_Query_Cache::hasCacheItem( 'id_from_meta_cache', $index ) ) {
			$this->was_last_fetch_from_cache = true;
			$cache_item                      = WPML_Media_Attachments_Query_Cache::getCacheItem( 'id_from_meta_cache', $index );
			return $cache_item ? $cache_item['post_id'] : null;
		}

		$sql = $this->wpdb->prepare(
			"SELECT post_id 
			FROM {$this->wpdb->postmeta} p 
			JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.post_id 
			WHERE p.meta_key = %s 
			AND p.meta_value = %s 
			AND t.element_type = 'post_attachment' 
			AND t.language_code = %s",
			'_wp_attached_file',
			$relative_path,
			$language
		);

		$attachment_id = $this->wpdb->get_var( $sql );

		return $attachment_id;
	}

	/**
	 * @return array
	 */
	private function getAllowedExtensionsForFilename() {
		return [
			'jpg', 'jpeg', 'jpe', 'gif', 'png', 'bmp', 'tiff', 'tif', 'webp', 'ico', 'heic',
			'asf', 'asx', 'wmv', 'wmx', 'wm', 'avi', 'divx', 'flv', 'mov', 'qt', 'mpeg', 'mpg',
			'mpe', 'mp4', 'm4v', 'ogv', 'webm', 'mkv', '3gp', '3gpp', '3g2', '3gp2', 'txt', 'asc',
			'srt', 'csv', 'tsv', 'ics', 'rtx', 'vtt', 'dfxp',
			'mp3', 'm4a', 'm4b', 'aac', 'ra', 'ram', 'wav', 'ogg', 'oga', 'flac', 'mid', 'midi', 'wma',
			'wax', 'mka', 'rtf', 'pdf', 'swf', 'tar', 'zip', 'gz', 'gzip', 'rar', '7z',
			'exe', 'psd', 'xcf', 'doc', 'pot', 'pps', 'ppt', 'wri', 'xla', 'xls', 'xlt', 'xlw', 'mdb', 'mpp',
			'docx', 'docm', 'dotx', 'dotm', 'xlsx', 'xlsm', 'xlsb', 'xltx', 'xltm', 'xlam',
			'pptx', 'pptm', 'ppsx', 'ppsm', 'potx', 'potm', 'ppam', 'sldx', 'sldm',
			'onetoc', 'onetoc2', 'onetmp', 'onepkg', 'oxps', 'xps', 'odt', 'odp', 'ods', 'odg', 'odc', 'odb', 'odf',
			'wp', 'wpd', 'key', 'numbers', 'pages',
		];
	}

	/**
	 * @param string $ext
	 *
	 * @return boolean
	 */
	private function hasAllowedExtension( $ext ) {
		$exts = $this->getAllowedExtensionsForFilename();
		return in_array( $ext, $exts );
	}

	/**
	 * @param array $source_items
	 *
	 * @return array
	 */
	private function partItemsWithExtAndWithout( $source_items ) {
		$with_ext    = [];
		$without_ext = [];

		foreach ( $source_items as $source_item ) {
			$url_parts = wpml_parse_url( $source_item );
			if ( isset( $url_parts['host'] ) && is_string( $url_parts['host'] ) ) {
				$domain            = $url_parts['host'];
				$domain_with_slash = $url_parts['host'] . '/';

				if ( Str::endsWith( $domain, $source_item ) || Str::endsWith( $domain_with_slash, $source_item ) ) {
					$without_ext[] = $source_item;
					continue;
				}
			}

			$maybe_ext = pathinfo( $source_item, PATHINFO_EXTENSION );

			if ( is_string( $maybe_ext ) && Str::len( $maybe_ext ) > 0 ) {
				if ( $this->hasAllowedExtension( $maybe_ext ) ) {
					$with_ext[] = $source_item;
				} else {
					$without_ext[] = $source_item;
				}
			} else {
				$without_ext[] = $source_item;
			}
		}

		return [ $with_ext, $without_ext ];
	}
}
