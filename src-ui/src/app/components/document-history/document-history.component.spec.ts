import { ComponentFixture, TestBed } from '@angular/core/testing'

import { DocumentHistoryComponent } from './document-history.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { of } from 'rxjs'
import { AuditLogAction } from 'src/app/data/auditlog-entry'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { NgbCollapseModule, NgbTooltipModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

describe('DocumentHistoryComponent', () => {
  let component: DocumentHistoryComponent
  let fixture: ComponentFixture<DocumentHistoryComponent>
  let documentService: DocumentService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [DocumentHistoryComponent, CustomDatePipe],
      providers: [DatePipe],
      imports: [
        HttpClientTestingModule,
        NgbCollapseModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbTooltipModule,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentHistoryComponent)
    documentService = TestBed.inject(DocumentService)
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
})
