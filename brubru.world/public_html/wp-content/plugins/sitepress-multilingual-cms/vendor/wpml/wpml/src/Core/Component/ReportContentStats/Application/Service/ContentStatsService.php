<?php

namespace WPML\Core\Component\ReportContentStats\Application\Service;

use WPML\Core\Component\ReportContentStats\Application\Query\CanCollectStatsQueryInterface;
use WPML\Core\Component\ReportContentStats\Application\Query\ContentStatsTranslatableTypesQueryInterface;
use WPML\Core\Component\ReportContentStats\Domain\ContentStatsCalculator;
use WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesStatsRepositoryInterface;
use WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesToCalculateRepositoryInterface;
use WPML\Core\SharedKernel\Component\Language\Application\Query\LanguagesQueryInterface;
use WPML\Core\SharedKernel\Component\Post\Application\Query\Dto\PostTypeDto;

class ContentStatsService {

  /** @var CanCollectStatsQueryInterface */
  private $canCollectStatsQuery;

  /** @var LastSentService */
  private $lastSentService;

  /** @var PostTypesToCalculateRepositoryInterface */
  private $postTypesToCalculateRepository;

  /** @var PostTypesStatsRepositoryInterface */
  private $postTypesStatsRepository;

  /** @var ContentStatsTranslatableTypesQueryInterface */
  private $translatableTypesQuery;

  /** @var LanguagesQueryInterface */
  private $languagesQuery;

  /** @var ContentStatsCalculator */
  private $contentStatsCalculator;


  public function __construct(
    CanCollectStatsQueryInterface $canCollectStatsQuery,
    LastSentService $lastSentService,
    PostTypesToCalculateRepositoryInterface $postTypesToCalculateRepository,
    PostTypesStatsRepositoryInterface $postTypesStatsRepository,
    ContentStatsTranslatableTypesQueryInterface $translatableTypesQuery,
    LanguagesQueryInterface $languagesQuery,
    ContentStatsCalculator $contentStatsCalculator
  ) {
    $this->canCollectStatsQuery           = $canCollectStatsQuery;
    $this->lastSentService                = $lastSentService;
    $this->postTypesToCalculateRepository = $postTypesToCalculateRepository;
    $this->postTypesStatsRepository       = $postTypesStatsRepository;
    $this->translatableTypesQuery         = $translatableTypesQuery;
    $this->languagesQuery                 = $languagesQuery;
    $this->contentStatsCalculator         = $contentStatsCalculator;
  }


  /**
   * @return false|string[]
   * @throws ContentStatsServiceException
   */
  public function processPostTypes() {
    if ( ! $this->canProcess() ) {
      throw new ContentStatsServiceException(
        'Stats collection is disabled'
      );
    }

    $postTypesToCalculate = $this->getOrInitPostTypesToCalculate();
    $defaultLanguageCode  = $this->languagesQuery->getDefaultCode();

    if ( empty( $postTypesToCalculate ) ) {
      return false;
    }

    return $this->processUntilTimeout( $postTypesToCalculate, $defaultLanguageCode );
  }


  public function canProcess(): bool {
    return $this->canCollectStatsQuery->get() &&
           $this->lastSentService->neverSentOrSent30DaysAgo();
  }


  /**
   * @param string[] $postTypesToCalculate
   * @param string $defaultLanguageCode
   * @param int $timeout
   *
   * @return string[]
   */
  private function processUntilTimeout(
    array $postTypesToCalculate,
    string $defaultLanguageCode,
    int $timeout = 1
  ): array {
    $processingTime     = 0;
    $processedPostTypes = [];

    foreach ( $postTypesToCalculate as $postType ) {
      if ( $processingTime >= $timeout ) {
        break;
      }

      $startTime = microtime( true );
      $this->processPostType( $postType, $defaultLanguageCode );
      $endTime = microtime( true );

      $processingTime += $endTime - $startTime;

      $processedPostTypes[] = $postType;
    }

    return $processedPostTypes;
  }


  /**
   * @param string $postType
   * @param string $defaultLanguageCode
   *
   * @return void
   */
  private function processPostType( string $postType, string $defaultLanguageCode ) {
    $postTypeStats = $this->contentStatsCalculator->calculateForPostType(
      $defaultLanguageCode,
      $postType
    );

    // Update the stats in DB when it could be calculated.
    if ( $postTypeStats ) {
      $this->postTypesStatsRepository->update( $postTypeStats );
    }

    // Remove the post type from the post types to calculate anyway, this way we don't
    // need to repeat the operation if the post type had no stats to calculate.
    $this->postTypesToCalculateRepository->removePostType( $postType );
  }


  /** @return void */
  public function resetPostTypesStatsData() {
    $this->postTypesToCalculateRepository->delete();
    $this->postTypesStatsRepository->delete();
  }


  /**
   * @return string[]
   */
  private function getOrInitPostTypesToCalculate(): array {
    $postTypesToCalculate = $this->postTypesToCalculateRepository->get();

    if ( $postTypesToCalculate === null ) {
      $postTypesToCalculate = array_map(
        function ( PostTypeDto $postType ) {
          return $postType->getId();
        },
        $this->translatableTypesQuery->getTranslatable()
      );

      $this->postTypesToCalculateRepository->init( $postTypesToCalculate );
    }

    return $postTypesToCalculate;
  }


}
