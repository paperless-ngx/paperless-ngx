import { DatePipe } from '@angular/common'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbPopoverModule,
  NgbTooltipModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { DocumentCardLargeComponent } from './document-card-large.component'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomFieldDisplayComponent } from '../../common/custom-field-display/custom-field-display.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const doc = {
  id: 10,
  title: 'Document 10',
  tags: [3, 4, 5],
  correspondent: 8,
  document_type: 10,
  storage_path: null,
  page_count: 8,
  notes: [
    {
      id: 11,
      note: 'This is some note content bananas',
    },
  ],
  content:
    'Cupcake ipsum dolor sit amet ice cream. Donut shortbread cheesecake caramels tiramisu pastry caramels chocolate bar. Tart tootsie roll muffin icing cotton candy topping sweet roll. Pie lollipop dragée sesame snaps donut tart pudding. Oat cake apple pie danish danish candy canes. Shortbread candy canes sesame snaps muffin tiramisu marshmallow chocolate bar halvah. Cake lemon drops candy apple pie carrot cake bonbon halvah pastry gummi bears. Sweet roll candy ice cream sesame snaps marzipan cookie ice cream. Cake cheesecake apple pie muffin candy toffee lollipop. Carrot cake oat cake cookie biscuit cupcake cake marshmallow. Sweet roll jujubes carrot cake cheesecake cake candy canes sweet roll gingerbread jelly beans. Apple pie sugar plum oat cake halvah cake. Pie oat cake chocolate cake cookie gingerbread marzipan. Lemon drops cheesecake lollipop danish marzipan candy.',
}

describe('DocumentCardLargeComponent', () => {
  let component: DocumentCardLargeComponent
  let fixture: ComponentFixture<DocumentCardLargeComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentCardLargeComponent,
        DocumentTitlePipe,
        CustomDatePipe,
        IfPermissionsDirective,
        SafeUrlPipe,
        IsNumberPipe,
        PreviewPopupComponent,
        CustomFieldDisplayComponent,
      ],
      imports: [
        RouterTestingModule,
        NgbPopoverModule,
        NgbTooltipModule,
        NgbProgressbarModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentCardLargeComponent)
    component = fixture.componentInstance
    component.document = doc
    fixture.detectChanges()
  })

  it('should display a document', () => {
    expect(fixture.nativeElement.textContent).toContain('Document 10')
    expect(fixture.nativeElement.textContent).toContain('Cupcake ipsum')
    expect(fixture.nativeElement.textContent).toContain('8 pages')
  })

  it('should trim content', () => {
    expect(component.contentTrimmed).toHaveLength(503) // includes ...
  })

  it('should display search hits with colored score', () => {
    // high
    component.document.__search_hit__ = {
      score: 0.9,
      rank: 1,
      highlights: 'cheesecake',
    }
    fixture.detectChanges()
    let search_hit = fixture.debugElement.query(By.css('.search-score'))
    expect(search_hit).not.toBeUndefined()
    expect(component.searchScoreClass).toEqual('success')

    // medium
    component.document.__search_hit__.score = 0.6
    fixture.detectChanges()
    search_hit = fixture.debugElement.query(By.css('.search-score'))
    expect(search_hit).not.toBeUndefined()
    expect(component.searchScoreClass).toEqual('warning')

    // low
    component.document.__search_hit__.score = 0.1
    fixture.detectChanges()
    search_hit = fixture.debugElement.query(By.css('.search-score'))
    expect(search_hit).not.toBeUndefined()
    expect(component.searchScoreClass).toEqual('danger')
  })

  it('should display note highlights', () => {
    component.document.__search_hit__ = {
      score: 0.9,
      rank: 1,
      note_highlights: '<span>bananas</span>',
    }
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('bananas')
    expect(component.searchNoteHighlights).toContain('<span>bananas</span>')
  })
})
