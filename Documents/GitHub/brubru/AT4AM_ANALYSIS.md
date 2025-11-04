# AT4AM System Analysis

## Overview
AT4AM (Amending Tool for 4 Million) is a legislative amendment tool developed by DFRI and built on the NSESA (National Standardized E-parliament Software Architecture) framework. The motto: "You have the power to change the law!"

## Architecture

### Technology Stack
- **Backend**: Java 1.8, Spring Framework 3.2.6
- **Frontend**: GWT (Google Web Toolkit) 2.5.0
- **Build Tool**: Maven
- **Database**: MySQL 5.6
- **Application Server**: Apache Tomcat 7
- **Document Format**: XML-based (Akoma Ntoso standard)

### Core Components

#### 1. nsesa-editor
- **Purpose**: Core amendment authoring interface
- **Type**: GWT-based rich web application
- **Version**: 0.12
- **License**: EUPL (European Union Public Licence)
- **Organization**: Originally developed for European Parliament

#### 2. nsesa-editor-an
- **Purpose**: Akoma Ntoso implementation for legislative documents
- **Features**:
  - Structured legislative document editing
  - Multi-language support
  - Standards-compliant XML formatting

#### 3. nsesa-server-api
- **Purpose**: RESTful API for editor backend services
- **Responsibilities**:
  - Document persistence
  - User authentication
  - Amendment workflow management
  - Version control

#### 4. nsesa-server-impl
- **Purpose**: Default implementation of server API
- **Features**:
  - Spring-based service layer
  - Database integration
  - Business logic for amendments

#### 5. nsesa-diff
- **Purpose**: Semi-structured document diffing
- **Key Classes**:
  - `DiffService`: Core diffing service
  - `WordExtractor`: Text tokenization
  - `ComplexDiffResult`: Structured diff results
  - `DiffMatchPatch`: Algorithm implementation

#### 6. nsesa-standalone
- **Purpose**: Standalone distribution package
- **Type**: Shell-based deployment scripts

## Key Features

### Amendment Authoring
- Rich text editing with WYSIWYG interface
- Structured amendment creation
- Support for multiple legislative formats
- Real-time collaboration capabilities

### Document Management
- XML-based document storage
- Version control
- Document comparison and merging
- Multi-format export

### Legislative Standards Support
- **Akoma Ntoso**: XML standard for legislative documents
- **European Parliament** format support
- **UN** document compatibility
- **National parliaments** (e.g., Italian Senate)

### User Management
- Role-based access control (ROLE_ADMIN, ROLE_USER)
- Authentication and authorization
- User workspace management

## Technical Details

### Database Configuration
- MySQL database: `nsesa`
- JDBC connection: `jdbc:mysql://localhost:3306/nsesa`
- Configuration file: `~/nsesa-server.properties`

### Deployment Architecture
```
┌─────────────────────────────────────┐
│        Apache Tomcat 7.x           │
├─────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────┐ │
│  │ editor.war   │  │ services.war│ │
│  │ (GWT Frontend)│  │ (Spring API)│ │
│  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│          MySQL 5.6 Database        │
└─────────────────────────────────────┘
```

### API Endpoints
- `/editor/amendment.html?documentID={id}` - Main editor interface
- RESTful services at `/services/*`

### Build Process
1. Clone repositories
2. Maven install for each module (10-30 minutes each):
   - nsesa-diff
   - nsesa-editor
   - nsesa-editor-an
   - nsesa-server-api
   - nsesa-server-impl
3. Deploy WAR files to Tomcat webapps
4. Configure database and properties files

## Limitations and Considerations

### Infrastructure
- Demo server at `demo.at4am.eu` may have broken links
- Requires significant disk space (5-10 GB)
- GWT compilation is memory-intensive

### Technology Age
- GWT 2.5.0 (released 2012) - outdated
- Spring 3.2.6 (released 2013) - outdated
- Java 1.7-1.8 target - older versions
- Maven Central repository links may be deprecated

### Documentation
- Minimal README files
- Limited API documentation
- Few code comments
- Sparse deployment guides

## Modernization Opportunities for Amendator

### Frontend
- Replace GWT with modern JavaScript framework (React, Vue, or Angular)
- Implement responsive design
- Add real-time collaboration (WebSockets)
- Modern rich text editor (ProseMirror, Slate, or TipTap)

### Backend
- Upgrade to Spring Boot 3.x
- Use Java 17+ LTS
- REST API with OpenAPI documentation
- GraphQL option for complex queries

### Database
- Modern ORM (JPA/Hibernate with Spring Data)
- PostgreSQL instead of MySQL
- Document versioning with proper migration strategy

### AI Integration
- **Anthropic Claude**:
  - Legislative text analysis
  - Amendment drafting assistance
  - Language translation
  - Policy impact analysis

- **OpenAI GPT-4**:
  - Alternative text generation
  - Summarization
  - Research assistance

### Social Integration
- **Google APIs**:
  - Google Drive for document storage
  - Gmail for notifications
  - Calendar for deadline tracking

- **LinkedIn**:
  - Professional networking
  - Expert consultation
  - Parliamentary contact management

### DevOps
- Docker containerization
- CI/CD pipeline (GitHub Actions)
- Cloud deployment (AWS, GCP, Azure)
- Automated testing

## Next Steps for Amendator

1. **Architecture Decision**:
   - Decide: Full rewrite vs. gradual modernization?
   - Choose: Monolithic vs. Microservices?
   - Select: Primary frontend framework

2. **MVP Features**:
   - Basic amendment editor
   - Document import/export
   - User authentication
   - AI-assisted drafting (using Anthropic/OpenAI)

3. **API Integration Plan**:
   - Google: Document storage and collaboration
   - LinkedIn: Professional networking
   - Anthropic: Primary AI for legislative analysis
   - OpenAI: Secondary AI for general text processing

4. **Database Design**:
   - Users and authentication
   - Documents and versions
   - Amendments and changes
   - Comments and collaboration
   - AI interaction history

## Resources

### GitHub Repositories
- https://github.com/e-parliament/nsesa-editor
- https://github.com/e-parliament/nsesa-editor-an
- https://github.com/e-parliament/nsesa-server-api
- https://github.com/e-parliament/nsesa-server-impl
- https://github.com/e-parliament/nsesa-diff
- https://github.com/at4ameu/at4am-documentation

### Documentation
- NSESA Documentation: http://nsesa.org/uploads/doc/documentation.html
- AT4AM Demo: http://demo.at4am.eu/editor/amendment.html

### Standards
- Akoma Ntoso: XML standard for parliamentary documents
- EUPL License: European Union Public Licence
