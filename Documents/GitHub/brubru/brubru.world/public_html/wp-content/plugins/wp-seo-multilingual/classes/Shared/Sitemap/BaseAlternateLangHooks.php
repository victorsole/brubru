<?php
namespace WPML\WPSEO\Shared\Sitemap;

use WPML\Element\API\Languages;
use WPML\FP\Fns;
use WPML\FP\Lst;
use WPML\FP\Obj;

use function WPML\FP\invoke;
use function WPML\FP\pipe;

abstract class BaseAlternateLangHooks implements \IWPML_Frontend_Action, \IWPML_DIC_Action {

	/** @var \WPML_Translation_Element_Factory $elementFactory */
	protected $elementFactory;

	/** @var array|null $activeLanguages */
	private $activeLanguages = null;
	/** @var array|null */
	private $mapLangToHrefLang = null;

	const KEY = 'alternateLangs';

	public function __construct( \WPML_Translation_Element_Factory $elementFactory ) {
		$this->elementFactory = $elementFactory;
	}

	/**
	 * @return string
	 */
	abstract protected function getUtils();

	/**
	 * @param string $urlset
	 *
	 * @return string
	 */
	public function addNamespace( $urlset ) {
		return str_replace( '>', ' xmlns:xhtml="http://www.w3.org/1999/xhtml">', $urlset );
	}

	/**
	 * @return string[]
	 */
	private function getActiveLanguages() {
		if ( null === $this->activeLanguages ) {
			$this->activeLanguages = array_keys( Languages::getActive() );
		}

		return $this->activeLanguages;
	}

	/**
	 * @param array $link
	 *
	 * @return array
	 */
	public function addAlternateLangDataToFirstLink( $link ) {
		$link[ self::KEY ] = [];
		foreach ( $this->getActiveLanguages() as $lang ) {
			$link[ self::KEY ][ $lang ] = apply_filters( 'wpml_permalink', $link['loc'], $lang );
		}

		return $link;
	}

	/**
	 * @param array  $entry
	 * @param string $type
	 * @param object $obj
	 *
	 * @return array
	 */
	public function addAlternateLangData( $entry, $type, $obj ) {
		if ( empty( $entry ) ) {
			return $entry;
		}

		list( $elements, $getPermalink, $isIndexable ) = $this->getEntryHelpers( $type, $obj );

		if ( $elements && $getPermalink && $isIndexable ) {
			/** @var callable(mixed, string):bool $isActiveLanguage */
			$isActiveLanguage = function ( $element, $language ) {
				return in_array( $language, $this->getActiveLanguages(), true );
			};

			/** @var callable(int, string):string $mapPermalink */
			$mapPermalink = function ( $id, $language ) use ( $getPermalink ) {
				return apply_filters( 'wpml_permalink', $getPermalink( $id ), $language );
			};

			/** @var callable(string):bool $isValidPermalink */
			$isValidPermalink = Fns::unary( 'is_string' );

			$entry[ static::KEY ] = wpml_collect( $elements )
				->filter( $isActiveLanguage )
				->filter( $isIndexable )
				->map( $mapPermalink )
				->filter( $isValidPermalink )
				->toArray();
		}

		return $entry;
	}

	/**
	 * @param string $type
	 * @param object $obj
	 *
	 * @return array{0: ?array, 1: ?callable, 2: ?callable}
	 */
	private function getEntryHelpers( $type, $obj ) {
		switch ( $type ) {
			case 'post':
				$getElements = pipe(
					[ $this->elementFactory, 'create_post' ],
					invoke( 'get_translations' ),
					Fns::map( invoke( 'get_element_id' ) )
				);
				return [
					$getElements( $obj->ID ),
					'get_permalink',
					[ $this->getUtils(), 'isIndexablePost' ],
				];
			case 'term':
				$getElements = function ( $termTaxonomyId ) {
					$translations = $this->elementFactory->create_term( $termTaxonomyId )->get_translations();
					$result       = [];

					foreach ( $translations as $langCode => $translation ) {
						$term = get_term_by( 'term_taxonomy_id', $translation->get_element_id() );
						if ( $term ) {
							$result[ $langCode ] = $term;
						}
					}

					return $result;
				};
				return [
					$getElements( $obj->term_taxonomy_id ),
					'get_term_link',
					[ $this->getUtils(), 'isIndexableTerm' ],
				];
			case 'user':
				$getElements = function ( $userId ) {
					return array_fill_keys( $this->getActiveLanguages(), $userId );
				};
				return [
					$getElements( $obj->ID ),
					'get_author_posts_url',
					Fns::always( true ),
				];
		}
		return [ null, null, null ];
	}

	/**
	 * @param string $output
	 * @param array  $url
	 *
	 * @return string
	 */
	public function insertAlternateLinks( $output, $url ) {
		$alternateLangs = Obj::prop( static::KEY, $url );

		if ( $alternateLangs ) {
			$defaultLang = apply_filters( 'wpml_default_language', false );
			if ( $defaultLang && isset( $alternateLangs[ $defaultLang ] ) ) {
				$alternateLangs['x-default'] = $alternateLangs[ $defaultLang ];
			}

			$output = str_replace( '</loc>', '</loc>' . $this->getAlternateLinks( $alternateLangs ), $output );
		}

		return $output;
	}

	/**
	 * @param array $alternateLangs
	 *
	 * @return string
	 */
	private function getAlternateLinks( $alternateLangs ) {
		$buildAlternateLink = function ( $url, $lang ) {
			return '<xhtml:link rel="alternate" hreflang="' . esc_attr( $this->getHrefLangForLang( $lang ) ) . '" href="' . esc_url( $url ) . '" />';
		};

		$links = wpml_collect( $alternateLangs )
			->map( $buildAlternateLink )
			->implode( "\n\t\t" );

		return $links ? "\n\t\t" . $links : '';
	}

	/**
	 * @param string $lang
	 *
	 * @return string
	 */
	private function getHrefLangForLang( $lang ) {
		if ( is_null( $this->mapLangToHrefLang ) ) {
			$this->mapLangToHrefLang = Lst::pluck( 'tag', (array) apply_filters( 'wpml_active_languages', null, [] ) );
		}

		return $this->mapLangToHrefLang[ $lang ] ?? $lang;
	}
}
