<?php

namespace WPML\WPSEO\YoastSEO\Terms\Meta;

use SitePress;
use WPML\WPSEO\YoastSEO\Utils;
use WPSEO_Taxonomy_Meta;
use WPML\LIB\WP\Hooks as WPHooks;

use function WPML\FP\spreadArgs;

class Hooks implements \IWPML_Frontend_Action, \IWPML_Backend_Action, \IWPML_DIC_Action {

	const PACKAGE = [
		'kind'      => 'Yoast SEO',
		'kind_slug' => 'yoast-seo',
		'name'      => 'term-meta',
		'title'     => 'Term Meta',
	];

	const FIELDS = [
		Utils::KEY_META_TITLE => 'SEO Title',
		Utils::KEY_META_DESC  => 'Meta Description',
		'wpseo_bctitle'       => 'Breadcrumb Title',
		'wpseo_focuskw'       => 'Focus Keyword',
	];

	/**
	 * @var string|null
	 */
	private $wpSeoOptionName;

	/**
	 * @var SitePress
	 */
	private $sitepress;

	public function __construct( SitePress $sitepress ) {
		$this->sitepress = $sitepress;
	}

	public function add_hooks() {
		WPHooks::onFilter( 'wpml_active_string_package_kinds' )
			->then( spreadArgs( [ $this, 'addPackageKind' ] ) );

		if ( is_admin() ) {
			WPHooks::onAction( 'add_option', 10, 2 )
				->then( spreadArgs( [ $this, 'registerStrings' ] ) );
			WPHooks::onAction( 'update_option', 10, 3 )
				->then( spreadArgs( [ $this, 'registerUpdatedStrings' ] ) );
		} else {
			WPHooks::onFilter( 'option_' . $this->getWpSeoOptionName() )
				->then( spreadArgs( [ $this, 'translateStrings' ] ) );
		}
	}

	/**
	 * @param array $kinds
	 *
	 * @return array
	 */
	public function addPackageKind( $kinds ) {
		$kinds[ self::PACKAGE['kind_slug'] ] = [
			'title'  => self::PACKAGE['kind'],
			'slug'   => self::PACKAGE['kind_slug'],
			'plural' => self::PACKAGE['kind'],
		];

		return $kinds;
	}

	/**
	 * @return array
	 */
	private function getPackage() {
		return [
			'kind'      => self::PACKAGE['kind'],
			'kind_slug' => self::PACKAGE['kind_slug'],
			'name'      => self::PACKAGE['name'],
			'title'     => self::PACKAGE['title'],
		];
	}

	/**
	 * @param string $option
	 * @param mixed  $value
	 */
	public function registerStrings( $option, $value ) {
		if ( $option !== $this->getWpSeoOptionName() || ! is_array( $value ) ) {
			return;
		}

		$package = $this->getPackage();

		do_action( 'wpml_start_string_package_registration', $package );

		foreach ( $value as $taxonomy => $terms ) {
			if ( ! is_array( $terms ) ) {
				continue;
			}

			foreach ( $terms as $termId => $termMeta ) {
				if ( ! is_array( $termMeta ) ) {
					continue;
				}

				$term = get_term( $termId, $taxonomy );
				if ( is_wp_error( $term ) ) {
					continue;
				}

				if ( ! $this->sitepress->is_original_content_filter( false, $termId, 'tax_' . $taxonomy ) ) {
					continue;
				}

				foreach ( self::FIELDS as $field => $fieldTitle ) {
					if ( ! empty( $termMeta[ $field ] ) ) {
						$stringName  = $this->buildStringName( $taxonomy, $termId, $field );
						$stringTitle = $fieldTitle . ': ' . $term->name;

						do_action(
							'wpml_register_string',
							$termMeta[ $field ],
							$stringName,
							$package,
							$stringTitle,
							'LINE'
						);
					}
				}
			}
		}

		do_action( 'wpml_delete_unused_package_strings', $package );
	}

	/**
	 * @param string $option
	 * @param mixed  $oldValue
	 * @param mixed  $value
	 */
	public function registerUpdatedStrings( $option, $oldValue, $value ) {
		if ( $oldValue !== $value ) {
			$this->registerStrings( $option, $value );
		}
	}

	/**
	 * @return string
	 */
	private function getWpSeoOptionName() {
		if ( null === $this->wpSeoOptionName ) {
			$this->wpSeoOptionName = WPSEO_Taxonomy_Meta::get_instance()->option_name;
		}

		return $this->wpSeoOptionName;
	}

	/**
	 * @param mixed $value
	 *
	 * @return mixed
	 */
	public function translateStrings( $value ) {
		if ( ! is_array( $value ) ) {
			return $value;
		}

		$package = $this->getPackage();

		foreach ( $value as $taxonomy => $terms ) {
			if ( ! is_array( $terms ) ) {
				continue;
			}

			foreach ( $terms as $termId => $termMeta ) {
				if ( ! is_array( $termMeta ) ) {
					continue;
				}

				if ( ! $this->sitepress->is_original_content_filter( false, $termId, 'tax_' . $taxonomy ) ) {
					continue;
				}

				foreach ( self::FIELDS as $field => $fieldTitle ) {
					if ( ! empty( $termMeta[ $field ] ) ) {
						$translatedValue = apply_filters(
							'wpml_translate_string',
							$termMeta[ $field ],
							$this->buildStringName( $taxonomy, $termId, $field ),
							$package
						);

						if ( $translatedValue && $translatedValue !== $value[ $taxonomy ][ $termId ][ $field ] ) {
							$translatedTermId = $this->sitepress->get_object_id( $termId, $taxonomy, false );
							if ( $translatedTermId ) {
								$value[ $taxonomy ][ $translatedTermId ][ $field ] = $translatedValue;
							}
						}
					}
				}
			}
		}

		return $value;
	}

	/**
	 * @param string $taxonomy
	 * @param int    $termId
	 * @param string $field
	 *
	 * @return string
	 */
	private function buildStringName( $taxonomy, $termId, $field ) {
		return $taxonomy . '-' . $termId . '-' . $field;
	}
}
