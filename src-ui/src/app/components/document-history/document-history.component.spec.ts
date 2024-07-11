import { ComponentFixture, TestBed } from '@angular/core/testing'

import { DocumentHistoryComponent } from './document-history.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { of } from 'rxjs'
import { AuditLogAction } from 'src/app/data/auditlog-entry'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { NgbCollapseModule, NgbTooltipModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { DataType } from 'src/app/data/datatype'

describe('DocumentHistoryComponent', () => {
  let component: DocumentHistoryComponent
  let fixture: ComponentFixture<DocumentHistoryComponent>
  let documentService: DocumentService
  let correspondentService: CorrespondentService
  let documentTypeService: DocumentTypeService
  let storagePathService: StoragePathService
  let userService: UserService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [DocumentHistoryComponent, CustomDatePipe],
      imports: [
        NgbCollapseModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbTooltipModule,
      ],
      providers: [
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentHistoryComponent)
    documentService = TestBed.inject(DocumentService)
    correspondentService = TestBed.inject(CorrespondentService)
    documentTypeService = TestBed.inject(DocumentTypeService)
    storagePathService = TestBed.inject(StoragePathService)
    userService = TestBed.inject(UserService)
    component = fixture.componentInstance
  })

  it('should get audit log entries on init', () => {
    const getHistorySpy = jest.spyOn(documentService, 'getHistory')
    getHistorySpy.mockReturnValue(
      of([
        {
          id: 1,
          actor: {
            id: 1,
            username: 'user1',
          },
          action: AuditLogAction.Create,
          timestamp: '2021-01-01T00:00:00Z',
          remote_addr: '1.2.3.4',
          changes: {
            title: ['old title', 'new title'],
          },
        },
      ])
    )
    component.documentId = 1
    fixture.detectChanges()
    expect(getHistorySpy).toHaveBeenCalledWith(1)
  })

  it('getPrettyName should return the correspondent name', () => {
    const correspondentId = '1'
    const correspondentName = 'John Doe'
    const getCachedSpy = jest
      .spyOn(correspondentService, 'getCached')
      .mockReturnValue(of({ name: correspondentName }))
    component
      .getPrettyName(DataType.Correspondent, correspondentId)
      .subscribe((result) => {
        expect(result).toBe(correspondentName)
      })
    expect(getCachedSpy).toHaveBeenCalledWith(parseInt(correspondentId))
    // no correspondent found
    getCachedSpy.mockReturnValue(of(null))
    component
      .getPrettyName(DataType.Correspondent, correspondentId)
      .subscribe((result) => {
        expect(result).toBe(correspondentId)
      })
  })

  it('getPrettyName should return the document type name', () => {
    const documentTypeId = '1'
    const documentTypeName = 'Invoice'
    const getCachedSpy = jest
      .spyOn(documentTypeService, 'getCached')
      .mockReturnValue(of({ name: documentTypeName }))
    component
      .getPrettyName(DataType.DocumentType, documentTypeId)
      .subscribe((result) => {
        expect(result).toBe(documentTypeName)
      })
    expect(getCachedSpy).toHaveBeenCalledWith(parseInt(documentTypeId))
    // no document type found
    getCachedSpy.mockReturnValue(of(null))
    component
      .getPrettyName(DataType.DocumentType, documentTypeId)
      .subscribe((result) => {
        expect(result).toBe(documentTypeId)
      })
  })

  it('getPrettyName should return the storage path path', () => {
    const storagePathId = '1'
    const storagePath = '/path/to/storage'
    const getCachedSpy = jest
      .spyOn(storagePathService, 'getCached')
      .mockReturnValue(of({ path: storagePath }))
    component
      .getPrettyName(DataType.StoragePath, storagePathId)
      .subscribe((result) => {
        expect(result).toBe(storagePath)
      })
    expect(getCachedSpy).toHaveBeenCalledWith(parseInt(storagePathId))
    // no storage path found
    getCachedSpy.mockReturnValue(of(null))
    component
      .getPrettyName(DataType.StoragePath, storagePathId)
      .subscribe((result) => {
        expect(result).toBe(storagePathId)
      })
  })

  it('getPrettyName should return the owner username', () => {
    const ownerId = '1'
    const ownerUsername = 'user1'
    const getCachedSpy = jest
      .spyOn(userService, 'getCached')
      .mockReturnValue(of({ username: ownerUsername }))
    component.getPrettyName('owner', ownerId).subscribe((result) => {
      expect(result).toBe(ownerUsername)
    })
    expect(getCachedSpy).toHaveBeenCalledWith(parseInt(ownerId))
    // no user found
    getCachedSpy.mockReturnValue(of(null))
    component.getPrettyName('owner', ownerId).subscribe((result) => {
      expect(result).toBe(ownerId)
    })
  })

  it('getPrettyName should return the value as is for other types', () => {
    const id = '123'
    component.getPrettyName('other', id).subscribe((result) => {
      expect(result).toBe(id)
    })
  })
})
