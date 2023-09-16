import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { ConsumptionTemplateService } from './consumption-template.service'

commonAbstractPaperlessServiceTests(
  'consumption_templates',
  ConsumptionTemplateService
)
