<?php

// phpcs:ignoreFile Squiz.NamingConventions.ValidVariableName.MemberNotCamelCaps
namespace WPML\Legacy\Component\WordsToTranslate\Domain\Job;

use WPML\Core\Component\WordsToTranslate\Domain\Job\Query\JobQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Provider as ProviderPost;
use WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Provider as ProviderStringBatch;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Provider as ProviderStringPackage;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;
use WPML\PHP\Exception\InvalidArgumentException;


class JobQuery implements JobQueryInterface {


  /** @var array<int, Job> */
  private $jobs = [];

  /** @var array<int, ?int> */
  private $wordsToTranslateCount = [];

  /** @var array<int, ?int> */
  private $automaticTranslationCosts = [];

  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return string
   */
  public function getSourceLang( $id ) {
    return $this->getJob( $id )->sourceLanguage;
  }

  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return string
   */
  public function getTargetLang( $id ) {
    return $this->getJob( $id )->targetLanguage;
  }


  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return int[]
   */
  public function getPreviousAteJobIds( $id ) {
    return $this->getJob( $id )->previousAteJobIds;
  }


  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return bool
   */
  public function isAutomatic( $id ) {
    return $this->getJob( $id )->isAutomatic;
  }


  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return int
   */
  public function getJobItemId( $id ) {
    return $this->getJob( $id )->itemId;
  }


  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return string
   */
  public function getJobItemType( $id ) {
    return $this->getJob( $id )->itemType;
  }


  /**
   * @param int $id
   *
   * @throws InvalidArgumentException
   *
   * @return TranslatableDTO[]
   */
  public function getContent( $id ) {
    return $this->getJob( $id )->content;
  }


  public function getWordsToTranslate( $id ) {
    if ( ! isset( $this->wordsToTranslateCount[ $id ] ) ) {
      $this->fetchWordsToTranslateAndAutomaticCosts( $id );
    }

    return $this->wordsToTranslateCount[ $id ];
  }


  public function getAutomaticTranslationCosts( $id ) {
    if ( ! isset( $this->automaticTranslationCosts[ $id ] ) ) {
      $this->fetchWordsToTranslateAndAutomaticCosts( $id );
    }

    return $this->automaticTranslationCosts[ $id ];
  }


  /** @return void */
  private function fetchWordsToTranslateAndAutomaticCosts( int $id ) {
    $wpdb = $GLOBALS['wpdb'];

    $row = $wpdb->get_row(
      $wpdb->prepare(
        "SELECT
          wpml_words_to_translate_count,
          wpml_automatic_translation_costs
        FROM
          {$wpdb->prefix}icl_translate_job
        WHERE
          job_id = %d",
        $id
      )
    );

    $this->wordsToTranslateCount[ $id ] = $row
      ? (
        is_numeric( $row->wpml_words_to_translate_count )
          ? (int) $row->wpml_words_to_translate_count
          : null
      )
      : null;

    $this->automaticTranslationCosts[ $id ] = $row
      ? (
        is_numeric( $row->wpml_automatic_translation_costs )
          ? (int) $row->wpml_automatic_translation_costs
          : null
        )
      : null;
  }

  /**
   * @param int $id
   *
   * @throws InvalidArgumentException Job for given id could not be found.
   *
   * @return Job
   */
  private function getJob( $id ) {
    if ( ! isset( $this->jobs[ $id ] ) ) {
      $wpdb = $GLOBALS['wpdb'];

      $job = null;

      if ( function_exists( 'wpml_tm_load_job_factory' ) ) {
        $jobFactory = \wpml_tm_load_job_factory();
        if ( is_object( $jobFactory ) && method_exists( $jobFactory, 'get_translation_job_as_stdclass' ) ) {
          $job = $jobFactory->get_translation_job_as_stdclass( $id );
        }
      }

      if ( ! $job ) {
        throw new InvalidArgumentException(
          sprintf(
            'Job with id %d not found',
            $id
          )
        );
      }

      if (
        ! is_object( $job )
        || ! isset( $job->rid )
        || ! isset( $job->source_language_code )
        || ! isset( $job->language_code )
        || ! isset( $job->automatic )
        || ! isset( $job->original_doc_id )
        || ! isset( $job->original_post_type )
        || ! isset( $job->elements ) || ! is_array ( $job->elements )
      ) {
        throw new InvalidArgumentException(
          sprintf(
            'Job with id %d does not contain all required fields',
            $id
          )
        );
      }


      $content = [];

      foreach ( $job->elements as $element ) {
        if (
          ! is_object( $element )
          || ! isset( $element->field_translate )
          || ! isset( $element->field_type )
          || ! isset( $element->field_data )
          || ! isset( $element->field_format )
        ) {
          throw new InvalidArgumentException(
            sprintf(
              'Job with id %d does not contain all required element fields',
              $id
            )
          );
        }
        if( ! $element->field_translate ) {
          continue;
        }

        $content[] = new TranslatableDTO(
          $element->field_type,
          $element->field_data,
          $element->field_format
        );
      }

      // Find previous conmpleted job for the same item.
      $previousAteJobIds = $wpdb->get_col(
        $wpdb->prepare(
          "SELECT editor_job_id
          FROM {$wpdb->prefix}icl_translate_job j
          WHERE rid = %d
          AND j.completed_date IS NOT NULL
          AND j.editor = 'ate'
          ORDER BY j.completed_date DESC
          LIMIT 15",
          $job->rid
        )
      );

      $previousAteJobIds = array_map( 'intval', $previousAteJobIds );

      $this->jobs[ $id ] = new Job(
        (int) $job->original_doc_id,
        $this->convertType( $job->original_post_type ),
        $job->source_language_code,
        $job->language_code,
        (bool) $job->automatic,
        $previousAteJobIds,
        $content
      );
    }

    return $this->jobs[ $id ];
  }


  /**
   * Converts raw data to a specific type.
   *
   * @param string $rawType
   *
   * @throws InvalidArgumentException Given rawType is unknown.
   *
   * @return string
   */
  private function convertType( $rawType ) {
    if ( strpos( $rawType, 'post_' ) === 0 ) {
      return ProviderPost::TYPE;
    }

    if ( strpos( $rawType, 'st-batch_strings' ) === 0 ) {
      return ProviderStringBatch::TYPE;
    }

    if ( strpos( $rawType, 'package_' ) === 0 ) {
      return ProviderStringPackage::TYPE;
    }

    throw new InvalidArgumentException(
      sprintf(
        'Raw data with type %s is not supported',
        $rawType
      )
    );
  }


}


/**
 * File internal class Job
 */
class Job { /** @var int */
  public $itemId;

  /** @var string */
  public $itemType;

  /** @var string */
  public $sourceLanguage;

  /** @var string */
  public $targetLanguage;

  /** @var bool */
  public $isAutomatic;

  /** @var int[] */
  public $previousAteJobIds;

  /** @var TranslatableDTO[] */
  public $content = [];



  /**
   * @param int $itemId
   * @param string $itemType
   * @param string $sourceLanguage
   * @param string $targetLanguage
   * @param bool $isAutomatic
   * @param int[] $previousAteJobIds
   * @param TranslatableDTO[] $content
   */
  public function __construct(
    $itemId,
    $itemType,
    $sourceLanguage,
    $targetLanguage,
    $isAutomatic,
    $previousAteJobIds,
    $content
  ) {
    $this->itemId = $itemId;
    $this->itemType = $itemType;
    $this->sourceLanguage = $sourceLanguage;
    $this->targetLanguage = $targetLanguage;
    $this->isAutomatic = $isAutomatic;
    $this->previousAteJobIds = $previousAteJobIds;
    $this->content = $content;
  }


}
