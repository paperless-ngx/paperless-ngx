import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { TagComponent } from '../../common/tag/tag.component'
import { DocumentCardSmallComponent } from './document-card-small.component'

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
  content:
    'Cupcake ipsum dolor sit amet ice cream. Donut shortbread cheesecake caramels tiramisu pastry caramels chocolate bar. Tart tootsie roll muffin icing cotton candy topping sweet roll. Pie lollipop dragée sesame snaps donut tart pudding. Oat cake apple pie danish danish candy canes. Shortbread candy canes sesame snaps muffin tiramisu marshmallow chocolate bar halvah. Cake lemon drops candy apple pie carrot cake bonbon halvah pastry gummi bears. Sweet roll candy ice cream sesame snaps marzipan cookie ice cream. Cake cheesecake apple pie muffin candy toffee lollipop. Carrot cake oat cake cookie biscuit cupcake cake marshmallow. Sweet roll jujubes carrot cake cheesecake cake candy canes sweet roll gingerbread jelly beans. Apple pie sugar plum oat cake halvah cake. Pie oat cake chocolate cake cookie gingerbread marzipan. Lemon drops cheesecake lollipop danish marzipan candy.',
}

describe('DocumentCardSmallComponent', () => {
  let component: DocumentCardSmallComponent
  let fixture: ComponentFixture<DocumentCardSmallComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        RouterTestingModule,
        NgxBootstrapIconsModule.pick(allIcons),
        DocumentCardSmallComponent,
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
    jest.useFakeTimers()
  })

  it('should show the card', () => {
    expect(component.show).toBeFalsy()
    component.ngAfterViewInit()
    jest.advanceTimersByTime(100)
    expect(component.show).toBeTruthy()
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

  it('should try to close the preview on mouse leave', () => {
    component.popupPreview = {
      close: jest.fn(),
    } as any
    component.mouseLeaveCard()
    expect(component.popupPreview.close).toHaveBeenCalled()
  })
})
