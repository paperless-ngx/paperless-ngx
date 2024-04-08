import { ComponentFixture, TestBed } from '@angular/core/testing'

import { AuditLogComponent } from './audit-log.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { of } from 'rxjs'
import { AuditLogAction } from 'src/app/data/auditlog-entry'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { NgbCollapseModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

describe('AuditLogComponent', () => {
  let component: AuditLogComponent
  let fixture: ComponentFixture<AuditLogComponent>
  let documentService: DocumentService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [AuditLogComponent, CustomDatePipe],
      providers: [DatePipe],
      imports: [
        HttpClientTestingModule,
        NgbCollapseModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(AuditLogComponent)
    documentService = TestBed.inject(DocumentService)
    component = fixture.componentInstance
  })

  it('should get audit log entries on init', () => {
    const getAuditLogSpy = jest.spyOn(documentService, 'getAuditLog')
    getAuditLogSpy.mockReturnValue(
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
    expect(getAuditLogSpy).toHaveBeenCalledWith(1)
  })

  it('should toggle entry', () => {
    const entry = {
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
    }
    component.toggleEntry(entry)
    expect(component.openEntries.has(1)).toBe(true)
    component.toggleEntry(entry)
    expect(component.openEntries.has(1)).toBe(false)
  })
})
