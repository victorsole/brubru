<?php
namespace WPML\WPSEO\RankMathSEO;

use RankMath\Helper;

class Utils {

	/**
	 * @param int $postId
	 *
	 * @return bool
	 */
	public static function isIndexablePost( $postId ) {
		return Helper::is_post_indexable( $postId );
	}

	/**
	 * @param \WP_Term $term
	 *
	 * @return bool
	 */
	public static function isIndexableTerm( $term ) {
		return Helper::is_term_indexable( $term );
	}
}
