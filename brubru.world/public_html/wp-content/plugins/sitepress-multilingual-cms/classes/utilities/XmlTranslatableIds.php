<?php

namespace WPML\Utils;

use WPML\Convert\Ids;
use WPML\FP\Obj;
use WPML\FP\Lst;
use WPML\FP\Str;

class XmlTranslatableIds {

	const TYPE_POST_IDS     = 'post-ids';
	const TYPE_TAXONOMY_IDS = 'taxonomy-ids';

	/**
	 * @param array $entry Top level key entry from the raw XML settings array.
	 * @param array $path
	 *
	 * @return array
	 */
	public function findPaths( $entry, $path = [] ) {
		$currentKeys = $this->normalizeKeys( (array) Obj::prop( 'key', $entry ) );
		$entryPaths  = [];

		if ( $currentKeys ) {
			foreach ( $currentKeys as $currentKey ) {
				$currentName = Obj::path( [ 'attr', 'name' ], $currentKey );
				$currentPath = array_merge( $path, [ $currentName ] );
				$entryPaths  = array_merge( $entryPaths, $this->findPaths( $currentKey, $currentPath ) );
			}
		} else {
			if ( $this->hasTranslatableIds( $entry ) ) {
				$type                     = $this->getType( $entry );
				$pathToKey                = implode( '>', $path );
				$slug                     = $this->getSlug( $entry, $type );
				$entryPaths[ $pathToKey ] = [
					'type' => $type,
					'slug' => $slug,
				];
			}
		}

		return $entryPaths;
	}

	/**
	 * If a sequence has only one element, we will wrap it
	 * in order to have the same data shape as for multiple elements.
	 *
	 * @param array $data
	 *
	 * @return array
	 */
	private function normalizeKeys( $data ) {
		return isset( $data['value'] ) ? array( $data ) : $data;
	}

	/**
	 * @param array $entry
	 *
	 * @return bool
	 */
	public function hasTranslatableIds( $entry ) {
		$entry = Obj::path( [ 'attr', 'type' ], $entry );
		return in_array( $entry, [ self::TYPE_POST_IDS, self::TYPE_TAXONOMY_IDS ], true );
	}

	/**
	 * @param array $entry
	 *
	 * @return string
	 */
	public function getType( $entry ) {
		return Obj::pathOr( self::TYPE_POST_IDS, [ 'attr', 'type' ], $entry );
	}

	/**
	 * @param array  $entry
	 * @param string $type
	 *
	 * @return string
	 */
	public function getSlug( $entry, $type ) {
		return Obj::path( [ 'attr', 'sub-type' ], $entry ) ?: wpml_collect(
			[
				self::TYPE_POST_IDS     => Ids::ANY_POST,
				self::TYPE_TAXONOMY_IDS => Ids::ANY_TERM,
			]
		)->get( $type, Ids::ANY_POST );
	}

}
