<?php

namespace WPML\WPSEO\RankMathSEO\Sitemap\LangMode;

class DomainHooks implements \IWPML_Frontend_Action, \IWPML_DIC_Action {

	/** @var \SitePress */
	private $sitepress;

	/**
	 * @param \SitePress $sitepress
	 */
	public function __construct( \SitePress $sitepress ) {
		$this->sitepress = $sitepress;
	}

	public function add_hooks() {
		add_filter( 'rank_math/sitemap/entry', [ $this, 'excludeOtherLanguages' ], 10, 3 );
	}

	/**
	 * @param string $url
	 * @param string $type
	 * @param object $element
	 *
	 * @return string
	 */
	public function excludeOtherLanguages( $url, $type, $element ) {
		if ( 'post' === $type ) {
			$elementType = 'post_' . $element->post_type;
			$elementId   = $element->ID;
		} elseif ( 'term' === $type ) {
			$elementType = 'tax_' . $element->taxonomy;
			$elementId   = $element->term_id;
		} else {
			return $url;
		}

		$currentLanguage = $this->sitepress->get_current_language();
		$elementLanguage = $this->sitepress->get_element_language_details( $elementId, $elementType );

		if ( $elementLanguage && $currentLanguage !== $elementLanguage->language_code ) {
			return '';
		}

		return $url;
	}
}
