<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class SimpleXMLExtensionRequirement extends RequirementBase {
  const EXTENSION_NAME = 'simplexml';

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
    return 5;
  }


  public function getTitle(): string {
    return __( 'SimpleXML Extension', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'The %sSimpleXML extension%s is required to use %sXLIFF files%s in WPML. '
            .
            'The libxml PHP Module must also be version 2.7.8 or higher.',
            'wpml'
          ),
          '<a  href="https://www.php.net/manual/en/book.simplexml.php" target="_blank">',
          '</a>',
          '<a href="https://wpml.org/documentation/translating-your-contents/using-desktop-cat-tools" target="_blank">',
          '</a>',
          RequirementsConfig::MINIMUM_SIMPLEXML_VERSION
        ),
      ],
      [
        'type'    => 'alert',
        'message' => __(
          'Contact your hosting provider to install the SimpleXML PHP extension.',
          'wpml'
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    return $this->serverInfo->isExtensionLoaded( self::EXTENSION_NAME );
  }


  protected function getRequirementType(): string {
    return 'SIMPLEXML_EXTENSION';
  }


}
