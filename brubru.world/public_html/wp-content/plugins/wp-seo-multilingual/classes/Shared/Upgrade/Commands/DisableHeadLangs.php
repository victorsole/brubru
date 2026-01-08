<?php
namespace WPML\WPSEO\Shared\Upgrade\Commands;

use WPML\FP\Obj;
use WPML\WPSEO\Shared\Options;

class DisableHeadLangs implements Command {

	const KEY_COMPLETED = 'command_disable_head_langs_complete';

	public static function run() {
		if ( Options::get( self::KEY_COMPLETED ) ) {
			return;
		}

		if ( defined( 'WPSEO_VERSION' ) ) {
			$options = get_option( 'wpseo' );
			if ( $options && $options['enable_xml_sitemap'] ) {
				self::disableHeadLangsWithNotice();
			}
		}

		if ( defined( 'RANK_MATH_VERSION' ) ) {
			self::disableHeadLangsWithNotice();
		}

		Options::set( self::KEY_COMPLETED, true );
	}

	private static function disableHeadLangsWithNotice() {
		if ( defined( 'WPML_SEO_ENABLE_SITEMAP_HREFLANG' ) && ! WPML_SEO_ENABLE_SITEMAP_HREFLANG ) {
			return;
		}

		if ( ! self::disableHeadLangs() ) {
			return;
		}

		self::addNotice();
	}

	/**
	 * @return bool
	 */
	private static function disableHeadLangs() {
		$seo = apply_filters( 'wpml_get_setting', [], 'seo' );
		if ( ! Obj::prop( 'head_langs', $seo ) ) {
			return false;
		}

		$seo['head_langs'] = 0;
		do_action( 'wpml_set_setting', 'seo', $seo, true );

		return true;
	}

	private static function addNotice() {
		$heading   = '<h2>' . esc_html__( 'Hreflang tags moved to your sitemap', 'wp-seo-multilingual' ) . '</h2>' . PHP_EOL;
		$text      = '<p>' . esc_html__( "To improve SEO and avoid duplicate hreflang data, WPML now adds hreflang tags only to your sitemap. We have disabled the hreflang tags in your page's <head> section.", 'wp-seo-multilingual' ) . '</p>' . PHP_EOL;
		$actionUrl = add_query_arg( [ 'page' => 'sitepress-multilingual-cms/menu/languages.php' ], admin_url( 'admin.php' ) ) . '#lang-sec-9-5';
		$actionTag = '<a href="' . esc_url( $actionUrl ) . '">';
		/* translators: %1$s %2$s: opening and closing tags for the link to WPML → Languages → SEO options */
		$action = '<p>' . sprintf( esc_html__( 'If you prefer to keep them in the <head>, you can re-enable this option in %1$sWPML → Languages → SEO options%2$s.', 'wp-seo-multilingual' ), $actionTag, '</a>' ) . '</p>' . PHP_EOL;

		$moreUrl  = 'https://wpml.org/documentation/plugins-compatibility/using-wordpress-seo-with-wpml/?utm_source=plugin&utm_medium=gui&utm_campaign=wpml-seo#create-multilingual-sitemaps';
		$moreLink = '<a class="wpml-external-link" target="_blank" href="' . esc_url( $moreUrl ) . '">' . esc_html__( 'Learn more', 'wp-seo-multilingual' ) . '</a>';

		$notice = \WPML_Notice::make( 'wpml-seo-disable-head-langs', $heading . $text . $action . $moreLink );
		$notice->set_restrict_to_screen_ids( [ 'dashboard', 'plugins' ] );
		$notice->set_css_class_types( 'info' );
		$notice->set_dismissible( true );

		wpml_get_admin_notices()->add_notice( $notice );
	}
}
