<?php

namespace WPML\WPSEO\RankMathSEO\Sitemap;

use WPML\WPSEO\RankMathSEO\Utils;
use WPML\WPSEO\Shared\Sitemap\BaseAlternateLangHooks;
use RankMath\Sitemap\Generator;

class AlternateLangHooks extends BaseAlternateLangHooks {

	public function add_hooks() {
		add_action(
			'parse_request',
			function ( $wp ) {
				if ( isset( $wp->query_vars['sitemap'] ) ) {
					$this->add_sitemap_hooks( $wp->query_vars['sitemap'] );
				}
			}
		);
	}

	/**
	 * @param string $type
	 */
	public function add_sitemap_hooks( $type ) {
		add_filter( 'rank_math/sitemap/' . $type . '_urlset', [ $this, 'addNamespace' ] );
		add_filter( 'rank_math/sitemap/' . $type . '_sitemap_url', [ $this, 'addAlternateLangDataToFirstLinks' ], 1, 2 );
		add_filter( 'rank_math/sitemap/entry', [ $this, 'addAlternateLangData' ], 10, 3 );
		add_filter( 'rank_math/sitemap/url', [ $this, 'insertAlternateLinks' ], 10, 2 );
		add_filter( 'rank_math/sitemap_url', [ $this, 'insertAlternateLinks' ], 10, 2 );
	}

	/**
	 * @return string
	 */
	protected function getUtils() {
		return Utils::class;
	}

	/**
	 * @param array     $url
	 * @param Generator $generator
	 *
	 * @return string|array
	 */
	public function addAlternateLangDataToFirstLinks( $url, $generator ) {
		global $wp_filter;

		if ( ! isset( $url[ self::KEY ] ) ) {
			$url = $this->addAlternateLangDataToFirstLink( $url );
		}

		/** @var callable(array):int $countCallbacksPerPriority */
		$countCallbacksPerPriority = function ( $callbacks ) {
			return count( $callbacks );
		};

		$totalCallbacks = wpml_collect( $wp_filter[ current_filter() ]->callbacks )
			->map( $countCallbacksPerPriority )
			->sum();

		// If we are the only callback, we must convert the array to a string by calling `$generator->sitemap_url`.
		// Otherwise, we should let the existing callback do that conversion.
		return $totalCallbacks > 1 ? $url : $generator->sitemap_url( $url );
	}
}
