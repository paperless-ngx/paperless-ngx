import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { PermissionsService } from '../services/permissions.service'
import { DocumentTypeService } from '../services/rest/document-type.service'
import { DocumentTypeNamePipe } from './document-type-name.pipe'

describe('DocumentTypeNamePipe', () => {
  let pipe: DocumentTypeNamePipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
  })

  // The pipe is a simple wrapper around ObjectNamePipe, see ObjectNamePipe for the actual tests.
  it('should be created', () => {
    pipe = new DocumentTypeNamePipe(
      TestBed.inject(PermissionsService),
      TestBed.inject(DocumentTypeService)
    )
    expect(pipe).toBeTruthy()
  })
})
