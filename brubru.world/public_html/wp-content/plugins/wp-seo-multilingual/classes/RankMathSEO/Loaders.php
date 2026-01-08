<?php

namespace WPML\WPSEO\RankMathSEO;

use WPML\FP\Logic;

class Loaders {

	/**
	 * @return array
	 */
	public static function get() {
		/** @var \SitePress $sitepress */
		global $sitepress;

		$isSitemapHrefLangEnabled = ! defined( 'WPML_SEO_ENABLE_SITEMAP_HREFLANG' ) || constant( 'WPML_SEO_ENABLE_SITEMAP_HREFLANG' );
		$langNegotiationType      = (int) $sitepress->get_setting( 'language_negotiation_type' );
		$isWooCommerceActive      = class_exists( \WooCommerce::class );

		return wpml_collect(
			[
				\WPML\WPSEO\Shared\Upgrade\Hooks::class => true,
				\WPML\WPSEO\Shared\Localization::class  => true,
				Sitemap\Hooks::class                    => true,
				Sitemap\AlternateLangHooks::class       => $isSitemapHrefLangEnabled,
				Slugs\HooksFactory::class               => true,
				TranslationJob\Hooks::class             => true,
				PrimaryCategory\Hooks::class            => true,
				Sitemap\LangMode\DirectoryHooks::class  => WPML_LANGUAGE_NEGOTIATION_TYPE_DIRECTORY === $langNegotiationType,
				Sitemap\LangMode\DomainHooks::class     => WPML_LANGUAGE_NEGOTIATION_TYPE_DOMAIN === $langNegotiationType,
				Compatibility\WooCommerce\Hooks::class  => $isWooCommerceActive,
			]
		)->filter( Logic::isTruthy() )
			->keys()
			->toArray();
	}
}
