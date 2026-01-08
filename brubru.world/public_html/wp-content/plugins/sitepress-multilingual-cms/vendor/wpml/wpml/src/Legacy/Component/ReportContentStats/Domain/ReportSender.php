<?php

namespace WPML\Legacy\Component\ReportContentStats\Domain;

use WPML\Core\Component\ReportContentStats\Domain\ContentStatsReport;
use WPML\Core\Component\ReportContentStats\Domain\ReportSenderInterface;

class ReportSender implements ReportSenderInterface {

  /** @var \WPML_Content_Stats_Sender */
  private $installerContentStatsSender;


  public function __construct( \WPML_Content_Stats_Sender $installerContentStatsSender ) {
    $this->installerContentStatsSender = $installerContentStatsSender;
  }


  public function send( ContentStatsReport $report ): bool {
    return $this->installerContentStatsSender->send( $report->getAsArray() );
  }


}
