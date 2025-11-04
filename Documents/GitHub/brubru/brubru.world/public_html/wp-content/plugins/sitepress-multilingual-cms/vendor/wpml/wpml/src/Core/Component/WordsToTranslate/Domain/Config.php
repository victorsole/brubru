<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

class Config {
  const KEY_WORDS_PER_IDEOGRAM = 'words_per_ideogram';

  // Only languages with specific settings are listed.
  const LANGS = [
    'ja' => [ // Japanese
      self::KEY_WORDS_PER_IDEOGRAM => 0.5
    ],
    'ko' => [ // Korean
      self::KEY_WORDS_PER_IDEOGRAM => 0.5
    ],
    'zh-hans' => [ // Chinese Simplified
      self::KEY_WORDS_PER_IDEOGRAM => 0.55
    ],
    'zh-hant' => [ // Chinese Traditional
      self::KEY_WORDS_PER_IDEOGRAM => 0.55
    ],
  ];

}
