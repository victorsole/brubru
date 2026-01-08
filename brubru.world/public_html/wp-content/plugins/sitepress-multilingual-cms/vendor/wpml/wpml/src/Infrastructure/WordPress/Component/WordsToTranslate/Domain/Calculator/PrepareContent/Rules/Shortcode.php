<?php

namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\ShortcodeInterface;

class Shortcode implements ShortcodeInterface {


  public function removeShortcodes( string $content ): string {
    // Don't do this:
    // $content = \strip_shortcodes( $content );
    // because even if a shortcode is registered on the site, it doesn't mean
    // that it's registered for WPML (wpml-config.xml). In that case the whole
    // shortcode is sent to ATE and ATE takes the inner content as text to translate.

    // Remove all shortcodes, but keep the inner content. Loop for nested shortcodes.
    do {
      $previousContent = $content;
      $content = preg_replace( '/\[([a-z0-9_-]+)(?:\s[^\]]*)?\](.*?)\[\/\1\]/is', '$2', $content ) ?? '';
    } while ( $content !== $previousContent );

    // Remove any shortcodes which are self-closing, like [foo /].
    $content = preg_replace( '/\[[a-z0-9_-]+(?:\s[^\]]*)?\/\]/i', '', $content ) ?? '';

    return $content;
  }


}
