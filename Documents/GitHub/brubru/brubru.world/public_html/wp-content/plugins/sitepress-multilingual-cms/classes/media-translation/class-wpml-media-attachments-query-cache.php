<?php

namespace WPML\Media\Classes;

/**
 * @see \WPML\Media\Classes\WPML_Media_Attachment_By_URL_Query::prefetchAllIdsFromGuids
 * @see \WPML_Post_Synchronization::sync_with_duplicates
 * @see https://onthegosystems.myjetbrains.com/youtrack/issue/wpmldev-3161/Expensive-queries-being-executed-on-save
 *
 * This class is used to optimize SQL queries during post synchronization with duplicates.
 *
 * WPML_Post_Synchronization::sync_with_duplicates runs a loop where it saves duplicate post data
 * for each language. As a result, the same query is executed separately for each language.
 *
 * This class allows executing a single query for all languages at once and then using cached
 * data in each iteration of the loop.
 */
class WPML_Media_Attachments_Query_Cache {

	/**
	 * @var array Cache items array
	 */
	private static $cache = [];

	/**
	 * Sometimes multiple rows are returned for one language(language_code field)/url(guid field) or language(language_code field)/relativePath(meta_value field) pair.
	 * We should set only first result in such cases same as with original get_var call, otherwise code with cache will not work in the same way as the original code.
	 * Example: [[post_id = 1, lang = en, url = otgs.com], [post_id = 2, lang = en, url = otgs.com]] => only first entry should be set to cache, second should be ignored.
	 *
	 * @param string     $cache_prop
	 * @param string     $item_index_in_cache
	 * @param array|null $item
	 */
	public static function setCacheItem( $cache_prop, $item_index_in_cache, $item ) {
		self::$cache[ $cache_prop ][ $item_index_in_cache ] = $item;
	}

	public static function getCacheItem( $cache_prop, $item_index_in_cache ) {
		return isset( self::$cache[ $cache_prop ][ $item_index_in_cache ] ) ? self::$cache[ $cache_prop ][ $item_index_in_cache ] : null;
	}

	public static function hasCacheItem( $cache_prop, $item_index_in_cache ) {
		return array_key_exists( $item_index_in_cache, isset( self::$cache[ $cache_prop ] ) ? self::$cache[ $cache_prop ] : [] );
	}
}
