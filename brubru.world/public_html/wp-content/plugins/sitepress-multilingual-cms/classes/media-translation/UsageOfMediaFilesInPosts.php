<?php

namespace WPML\MediaTranslation;

class UsageOfMediaFilesInPosts {
	const USAGES_AS_COPY_IN_POSTS = '_wpml_media_usage_in_posts_as_copy';
	const USAGES_AS_REFERENCE_IN_POSTS = '_wpml_media_usage_in_posts_as_reference';
	const USAGES_FIELD_NAME = '_wpml_media_usage_in_posts';

	/**
	 * @param int   $post_id
	 * @param array $last_copied_media_file_ids
	 * @param array $last_referenced_media_file_ids
	 * @param array $copied_media_file_ids
	 * @param array $referenced_media_file_ids
	 */
	public function updateUsages(
		$post_id,
		$last_copied_media_file_ids,
		$last_referenced_media_file_ids,
		$copied_media_file_ids,
		$referenced_media_file_ids
	) {
		$usages_in_posts_to_update = $this->getUsages(
			$post_id,
			$last_copied_media_file_ids,
			$last_referenced_media_file_ids,
			$copied_media_file_ids,
			$referenced_media_file_ids
		);

		foreach ( $usages_in_posts_to_update as $media_file_id => $usages ) {
			update_post_meta( $media_file_id, self::USAGES_FIELD_NAME, $usages );
		}
	}

	/**
	 * @param int   $post_id
	 * @param array $last_copied_media_file_ids
	 * @param array $last_referenced_media_file_ids
	 * @param array $copied_media_file_ids
	 * @param array $referenced_media_file_ids
	 * @param array $usages_cache
	 *
	 * @return array
	 */
	public function getUsages(
		$post_id,
		$last_copied_media_file_ids,
		$last_referenced_media_file_ids,
		$copied_media_file_ids,
		$referenced_media_file_ids,
		$usages_cache = []
	) {
		$equals = function( $a, $b ) {
			sort( $a );
			sort( $b );

			if ( count( $a ) != count( $b ) ) {
				return false;
			}

			for ( $x = 0; $x < count( $a ); $x++ ) {
				if ( $a[ $x ] != $b[ $x ] ) {
					return false;
				}
			}

			return true;
		};

		$all_media_file_ids = array_values(
			array_unique(
				array_merge(
					$copied_media_file_ids,
					$last_copied_media_file_ids,
					$referenced_media_file_ids,
					$last_referenced_media_file_ids
				)
			)
		);

		$usages_in_posts = [];

		foreach ( $all_media_file_ids as $media_file_id ) {
			$existing_usages_in_posts = [];
			/*
				When calling this function from a background tasks to process batch of posts in 1 request $media_file_id
				will always be setup, so we will always get usages from the cache(even if it not exists).
				So, second case should be never called from batch processing and no extra guards for get queries are required there.
			*/
			if ( array_key_exists( $media_file_id, $usages_cache ) ) {
				$existing_usages_in_posts = $usages_cache[ $media_file_id ];
			} else {
				$existing_usages_in_posts_as_copy      = $this->getUsagesAsCopy( $media_file_id );
				$existing_usages_in_posts_as_reference = $this->getUsagesAsReference( $media_file_id );

				if ( is_array( $existing_usages_in_posts_as_copy ) ) {
					$existing_usages_in_posts[ self::USAGES_AS_COPY_IN_POSTS ] = $existing_usages_in_posts_as_copy;
				}
				if ( is_array( $existing_usages_in_posts_as_reference ) ) {
					$existing_usages_in_posts[ self::USAGES_AS_REFERENCE_IN_POSTS ] = $existing_usages_in_posts_as_reference;
				}
			}
			$usages_in_posts[ $media_file_id ] = $existing_usages_in_posts;
			if ( ! array_key_exists( self::USAGES_AS_COPY_IN_POSTS, $usages_in_posts[ $media_file_id ] ) ) {
				$usages_in_posts[ $media_file_id ][ self::USAGES_AS_COPY_IN_POSTS ] = [];
			}
			if ( ! array_key_exists( self::USAGES_AS_REFERENCE_IN_POSTS, $usages_in_posts[ $media_file_id ] ) ) {
				$usages_in_posts[ $media_file_id ][ self::USAGES_AS_REFERENCE_IN_POSTS ] = [];
			}
		}

		$original_usages_in_posts = $usages_in_posts;

		$this->removeLastUsedMediaFileIdsByType( $post_id, $usages_in_posts, $last_copied_media_file_ids, self::USAGES_AS_COPY_IN_POSTS );
		$this->removeLastUsedMediaFileIdsByType( $post_id, $usages_in_posts, $last_referenced_media_file_ids, self::USAGES_AS_REFERENCE_IN_POSTS );
		$this->addNewUsedMediaFileIdsByType( $post_id, $usages_in_posts, $copied_media_file_ids, self::USAGES_AS_COPY_IN_POSTS );
		$this->addNewUsedMediaFileIdsByType( $post_id, $usages_in_posts, $referenced_media_file_ids, self::USAGES_AS_REFERENCE_IN_POSTS );

		$usages_in_posts_to_update = [];

		foreach ( $usages_in_posts as $media_file_id => $usages ) {
			$new_usages_copy  = $usages[ self::USAGES_AS_COPY_IN_POSTS ];
			$new_usages_ref   = $usages[ self::USAGES_AS_REFERENCE_IN_POSTS ];
			$orig_usages_copy = $original_usages_in_posts[ $media_file_id ][ self::USAGES_AS_COPY_IN_POSTS ];
			$orig_usages_ref  = $original_usages_in_posts[ $media_file_id ][ self::USAGES_AS_REFERENCE_IN_POSTS ];

			if ( $equals( $new_usages_copy, $orig_usages_copy ) && $equals( $new_usages_ref, $orig_usages_ref ) ) {
				continue;
			}

			$usages_in_posts_to_update[ $media_file_id ] = $usages;
		}

		return $usages_in_posts_to_update;
	}

	private function removeLastUsedMediaFileIdsByType( $post_id, &$usages_in_posts, $last_used_media_file_ids, $type ) {
		foreach ( $last_used_media_file_ids as $media_file_id ) {
			if ( ! in_array( $post_id, $usages_in_posts[ $media_file_id ][ $type ] ) ) {
				continue;
			}

			$usages_in_posts[ $media_file_id ][ $type ] = array_filter(
				$usages_in_posts[ $media_file_id ][ $type ],
				function( $value ) use ( $post_id ) {
					return $value != $post_id;
				}
			);
		}
	}

	private function addNewUsedMediaFileIdsByType( $post_id, &$usages_in_posts, $new_used_media_file_ids, $type ) {
		foreach ( $new_used_media_file_ids as $media_file_id ) {
			if ( in_array( $post_id, $usages_in_posts[ $media_file_id ][ $type ] ) ) {
				continue;
			}

			$usages_in_posts[ $media_file_id ][ $type ][] = $post_id;
		}
	}

	/**
	 * @return array
	 */
	public function getUsagesAsCopy( $media_file_id ) {
		return $this->getUsagesByType( $media_file_id, self::USAGES_AS_COPY_IN_POSTS );
	}

	/**
	 * @return array
	 */
	public function getUsagesAsReference( $media_file_id ) {
		return $this->getUsagesByType( $media_file_id, self::USAGES_AS_REFERENCE_IN_POSTS );
	}

	private function getUsagesByType( $media_file_id, $type ) {
		$usages = $this->getUsagesFromPostMeta( $media_file_id, self::USAGES_FIELD_NAME );

		if ( array_key_exists( $type, $usages ) ) {
			return $usages[ $type ];
		}

		$legacy_usages = $this->getUsagesFromPostMeta( $media_file_id, $type );

		return $legacy_usages;
	}

	public function getUsagesFromPostMeta( $media_file_id, $field_name ) {
		$usages = get_post_meta( $media_file_id, $field_name, true );
		return empty( $usages ) ? array() : $usages;
	}
}