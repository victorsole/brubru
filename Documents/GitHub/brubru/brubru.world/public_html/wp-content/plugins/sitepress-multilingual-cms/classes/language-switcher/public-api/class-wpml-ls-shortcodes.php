<?php
/**
 * Class WPML_LS_Shortcodes
 */
class WPML_LS_Shortcodes extends WPML_LS_Public_API {
	// Important: Same length for disabled variant.
	// Because plugins/themes may store the content serialized and a different
	// characters length would break the serialization.
	const LS                 = 'wpml_language_switcher';
	const LS_WIDGET          = 'wpml_language_selector_widget';
	const LS_FOOTER          = 'wpml_language_selector_footer';

	public function init_hooks() {
		if ( $this->sitepress->get_setting( 'setup_complete' ) ) {
			add_shortcode( self::LS, array( $this, 'callback' ) );

			// Backward compatibility.
			add_shortcode( self::LS_WIDGET, array( $this, 'callback' ) );
			add_shortcode( self::LS_FOOTER, array( $this, 'callback' ) );
		}
	}

	/**
	 * @param array|string $args
	 * @param string|null  $content
	 * @param string       $tag
	 *
	 * @return string
	 */
	public function callback( $args, $content = null, $tag = '' ) {
		$args = (array) $args;
		$args = $this->parse_legacy_shortcodes( $args, $tag );
		$args = $this->convert_shortcode_args_aliases( $args );

		return $this->render( $args );
	}


	/**
	 * @param array  $args
	 * @param string $tag
	 *
	 * @return mixed
	 */
	private function parse_legacy_shortcodes( $args, $tag ) {
		if ( 'wpml_language_selector_widget' === $tag ) {
			$args['type'] = 'custom';
		} elseif ( 'wpml_language_selector_footer' === $tag ) {
			$args['type'] = 'footer';
		}

		return $args;
	}

}
