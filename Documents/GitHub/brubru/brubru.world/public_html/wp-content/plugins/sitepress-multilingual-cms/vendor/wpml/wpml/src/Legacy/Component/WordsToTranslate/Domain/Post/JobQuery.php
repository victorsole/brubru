<?php

namespace WPML\Legacy\Component\WordsToTranslate\Domain\Post;

use WPML\Core\Component\WordsToTranslate\Domain\Post\JobDto;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Post;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Query\JobQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\Term;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\TermContent;
use WPML\Legacy\Component\WordsToTranslate\Domain\JobPackageTrait;

class JobQuery implements JobQueryInterface {
  use JobPackageTrait;

  /** @var array<int, array<mixed>> $jobPackages */
  private $jobPackages = [];


  /** @return JobDto */
  public function getContentToTranslateForLang( Post $post, string $lang ) {
    $jobPackage = $this->getJobPackage( $post, $lang );
    $translatableFields = $this->getTranslatableFields( $jobPackage );

    $content = '';

    foreach ( $translatableFields as $type => $data ) {
      // Skip terms.
      $isTerm = $this->getTermIdAndType( $type );
      if ( $isTerm ) {
        continue;
      }

      // All other content.
      $content .= $content ? ' ' . $data : $data;
    }

    return new JobDto( $content, array_keys( $translatableFields ) );
  }


  public function getTerms( Post $post ) {
    $jobPackage = $this->getJobPackage( $post );
    $translatableFields = $this->getTranslatableFields( $jobPackage );
    $terms = [];

    foreach ( $translatableFields as $type => $data ) {
      $termIdAndType = $this->getTermIdAndType( $type );
      if ( ! $termIdAndType ) {
        continue; // Skip other content than terms.
      }

      $termId = $termIdAndType[0];
      $termType = $termIdAndType[1];

      $termContent = new TermContent( $termId, $termType, $post->getSourceLang() );
      $termContent->setContent( $data );

      $term = isset( $terms[ $termId ] )
        ? $terms[ $termId ]
        : new Term( $termId );

      $term->addContent( $termContent );

      if ( ! isset( $terms[ $termId ] ) ) {
        $terms[ $termId ] = $term;
      }
    }

    return $terms;
  }


  /**
   * @param string $type
   *
   * @return ?array{int,string}
   */
  private function getTermIdAndType( $type ) {
    if ( strpos( $type, 't_' ) === 0 ) {
      return [(int) substr( $type, 2 ), 'name'];
    } elseif ( strpos( $type, 'tdesc_' ) === 0 ) {
      return [(int) substr( $type, 6 ), 'description'];
    } elseif ( strpos( $type, 'tfield-' ) === 0 && preg_match( '/tfield-(.*?)-(\d{1,})($|\_)/', $type, $matches ) ) {
      return [(int) $matches[2], $matches[1]];
    }

    return null;
  }


  /**
   * @param Post $post
   * @param ?string $lang
   *
   * @return array<string, string>
   */
  private function getJobPackage( Post $post, $lang = null ) {
    $package = isset( $this->jobPackages[ $post->getId() ] )
      ? $this->jobPackages[ $post->getId() ]
      : false;

    if ( ! $package ) {
      $this->wpmlElementTranslationPackage()
          ->do_action_before_creating_translation_package(
            \get_post( $post->getId() )
          );

      /** @var array<string, mixed> $package */
      $package = $this->wpmlElementTranslationPackage()
          ->create_translation_package( $post->getId(), true ) ?: false;

      $package = $this->filterCustomFields( $package, $post );

      $this->jobPackages[ $post->getId() ] = $package;
    }

    /** @var array<string, string> $package */
    $package = $lang
      ? $this->wpmlElementTranslationPackage()
        ->filter_translation_package_for_lang(
          $package,
          \get_post( $post->getId() ),
          $lang
        )
      : $package;

    return $package ?: [];
  }


  public function useThisContentForItem( $idItem, $content ) {
    $data = [ 'contents' => [] ];

    foreach ( $content as $part ) {
      $data['contents'][ $part->getType() ] = [
        'translate' => 1,
        'data'   => $part->getContent(),
        'format' => $part->getFormat(),
      ];
    }

    $this->jobPackages[ $idItem ] = $data;
  }


  /**
   * Filters custom fields from the package contents.
   *
   * @param array<string, mixed> $package
   * @param Post $post
   *
   * @return array<string, mixed>
   */
  private function filterCustomFields( $package, Post $post ) {
    $package['contents'] = isset( $package['contents'] ) && is_array( $package['contents'] )
      ? $package['contents']
      : [];

    $customFields = [];

    foreach ( array_keys( $package['contents'] ) as $type ) {
      if ( strpos( $type, 'field-' ) !== 0 ) {
        continue;
      }

      if ( preg_match( '/^field-(.*?)-\d+/', $type, $match ) ) {
          $customFields[] = $match[1];
      }
    }

    if ( $customFields ) {
      $allowedCustomFields = apply_filters(
        'wpml_words_count_custom_fields_to_count',
        array_unique( $customFields ),
        $post->getId()
      );

      $package['contents'] = array_filter(
        $package['contents'],
        function ( $type ) use ( $allowedCustomFields ) {
          if ( strpos( $type, 'field-' ) !== 0 ) {
            return true; // Keep non-custom fields.
          }

          foreach ( $allowedCustomFields as $allowedCustomField ) {
            if ( strpos( $type, 'field-' . $allowedCustomField ) === 0 ) {
              return true;
            }
          }

          return false; // Filter out custom fields not in the list.
        },
        ARRAY_FILTER_USE_KEY
      );
    }

    return $package;
  }


}
