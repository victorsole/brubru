<?php

namespace WPML\UserInterface\Web\Core\Component\ContentStats\Application\Endpoint\CalculateContentStats;

use WPML\Core\Component\ReportContentStats\Application\Service\ContentStatsService;
use WPML\Core\Component\ReportContentStats\Application\Service\ContentStatsServiceException;
use WPML\Core\Component\ReportContentStats\Application\Service\LastSentService;
use WPML\Core\Component\ReportContentStats\Application\Service\ReportPreparer\ReportPreparerService;
use WPML\Core\Component\ReportContentStats\Application\Service\ReportSender\ReportSenderService;
use WPML\Core\Port\Endpoint\EndpointInterface;

class ProcessContentStatsController implements EndpointInterface {

  /** @var LastSentService */
  private $lastSentService;

  /** @var ContentStatsService */
  private $contentStatsService;

  /** @var ReportPreparerService */
  private $reportPreparerService;

  /** @var ReportSenderService */
  private $reportSenderService;


  public function __construct(
    ContentStatsService $contentStatsService,
    LastSentService $lastSentService,
    ReportPreparerService $reportPreparerService,
    ReportSenderService $reportSenderService
  ) {
    $this->contentStatsService   = $contentStatsService;
    $this->lastSentService       = $lastSentService;
    $this->reportPreparerService = $reportPreparerService;
    $this->reportSenderService   = $reportSenderService;
  }


  public function handle( $requestData = null ): array {
    try {
      $processedPostTypes = $this->contentStatsService->processPostTypes();

      /**
       * In case $processedPostTypes is not FALSE, we return response and in next
       * iteration we decide if we should process more post types or send report.
       */

      if ( $processedPostTypes ) {
        return [
          'success' => true,
          'message' => 'Calculation done for post types: ' .
                       implode( ',', $processedPostTypes ),
        ];
      }

      /**
       * In case we don't have any post types to process anymore
       * we should start sending report and setting correct values in DB.
       */

      // Prepare report
      $preparedReport = $this->reportPreparerService->prepare();

      // Sending the report
      $reportSentSuccessfully = $this->reportSenderService->send( $preparedReport );

      /**
       * next we're going to update the last sent timestamp
       * and reset the post types stats data in DB for processing next month
       * this happens even if sending report failed, to not add overhead to the site.
       */

      // updating last sent to current timestamp
      $this->lastSentService->update( time() );

      // Resetting post types stats data in DB for processing next month
      $this->contentStatsService->resetPostTypesStatsData();

      if ( ! $reportSentSuccessfully ) {
        return [
          'success' => false,
          'message' => 'Error when sending report',
        ];
      }
    } catch ( ContentStatsServiceException $e ) {
      return [
        'success' => false,
        'message' => $e->getMessage(),
      ];
    }

    return [
      'success' => true,
      'message' => 'Report sent successfully!',
    ];
  }


}
