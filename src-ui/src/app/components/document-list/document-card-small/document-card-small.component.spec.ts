import { DatePipe } from '@angular/common'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
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
import { DocumentCardSmallComponent } from './document-card-small.component'
import { of } from 'rxjs'
import { By } from '@angular/platform-browser'
import { TagComponent } from '../../common/tag/tag.component'
import { Tag } from 'src/app/data/tag'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomFieldDisplayComponent } from '../../common/custom-field-display/custom-field-display.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const doc = {
  id: 10,
  title: 'Document 10',
  tags: [1, 2, 3, 4, 5, 6, 7, 8],
  correspondent: 8,
  document_type: 10,
  storage_path: null,
  page_count: 12,
  notes: [
    {
      id: 11,
      note: 'This is some note content bananas',
    },
  ],
  tags$: of([
    { id: 1, name: 'Tag1' },
    { id: 2, name: 'Tag2' },
    { id: 3, name: 'Tag3' },
    { id: 4, name: 'Tag4' },
    { id: 5, name: 'Tag5' },
    { id: 6, name: 'Tag6' },
    { id: 7, name: 'Tag7' },
    { id: 8, name: 'Tag8' },
  ]),
  content:
    'Cupcake ipsum dolor sit amet ice cream. Donut shortbread cheesecake caramels tiramisu pastry caramels chocolate bar. Tart tootsie roll muffin icing cotton candy topping sweet roll. Pie lollipop dragée sesame snaps donut tart pudding. Oat cake apple pie danish danish candy canes. Shortbread candy canes sesame snaps muffin tiramisu marshmallow chocolate bar halvah. Cake lemon drops candy apple pie carrot cake bonbon halvah pastry gummi bears. Sweet roll candy ice cream sesame snaps marzipan cookie ice cream. Cake cheesecake apple pie muffin candy toffee lollipop. Carrot cake oat cake cookie biscuit cupcake cake marshmallow. Sweet roll jujubes carrot cake cheesecake cake candy canes sweet roll gingerbread jelly beans. Apple pie sugar plum oat cake halvah cake. Pie oat cake chocolate cake cookie gingerbread marzipan. Lemon drops cheesecake lollipop danish marzipan candy.',
}

describe('DocumentCardSmallComponent', () => {
  let component: DocumentCardSmallComponent
  let fixture: ComponentFixture<DocumentCardSmallComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentCardSmallComponent,
        DocumentTitlePipe,
        CustomDatePipe,
        IfPermissionsDirective,
        SafeUrlPipe,
        TagComponent,
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

    fixture = TestBed.createComponent(DocumentCardSmallComponent)
    component = fixture.componentInstance
    component.document = Object.assign({}, doc)
    fixture.detectChanges()
  })

  it('should display page count', () => {
    expect(fixture.nativeElement.textContent).toContain('12 pages')
  })

  it('should display a document, limit tags to 5', () => {
    expect(fixture.nativeElement.textContent).toContain('Document 10')
    expect(
      fixture.debugElement.queryAll(By.directive(TagComponent))
    ).toHaveLength(5)
    component.document.tags = [1, 2]
    component.document.tags$ = of([{ id: 1 } as Tag, { id: 2 } as Tag])
    fixture.detectChanges()
    expect(
      fixture.debugElement.queryAll(By.directive(TagComponent))
    ).toHaveLength(2)
  })

  it('should increase limit tags to 6 if no notes', () => {
    component.document.notes = []
    fixture.detectChanges()
    expect(
      fixture.debugElement.queryAll(By.directive(TagComponent))
    ).toHaveLength(6)
  })
})
