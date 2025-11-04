<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class WordPressVersionRequirement extends RequirementBase {

  /** @var ServerInfoInterface */
  private $serverInfo;


  /**
   * Constructor.
   *
   * @param ServerInfoInterface $serverInfo The server info service.
   */
  public function __construct( ServerInfoInterface $serverInfo ) {
    $this->serverInfo = $serverInfo;
  }


  public function getId(): int {
    return 6;
  }


  public function getTitle(): string {
    return __( 'WordPress Version', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'Your WordPress version is outdated. WPML requires at least %s. ',
            'wpml'
          ),
          '<strong> WordPress ' . RequirementsConfig::MINIMUM_WP_VERSION
          . '</strong>'
        ),
      ],
      [
        'type'    => 'alert',
        'message' => sprintf(
          __(
            'Please update your WordPress installation to version %s or higher.',
            'wpml'
          ),
          RequirementsConfig::MINIMUM_WP_VERSION
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    return version_compare(
      $this->serverInfo->getWordPressVersion(),
      RequirementsConfig::MINIMUM_WP_VERSION,
      '>='
    );
  }


  protected function getRequirementType(): string {
    return 'WORDPRESS_VERSION';
  }


}
