import {
  importProvidersFrom,
  inject,
  provideAppInitializer,
  provideZoneChangeDetection,
} from '@angular/core'

import { DragDropModule } from '@angular/cdk/drag-drop'
import { DatePipe, registerLocaleData } from '@angular/common'
import {
  provideHttpClient,
  withFetch,
  withInterceptors,
  withInterceptorsFromDi,
} from '@angular/common/http'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { BrowserModule, bootstrapApplication } from '@angular/platform-browser'
import {
  NgbDateAdapter,
  NgbDateParserFormatter,
  NgbModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import {
  NgxBootstrapIconsModule,
  airplane,
  archive,
  arrowClockwise,
  arrowCounterclockwise,
  arrowDown,
  arrowDownUp,
  arrowLeft,
  arrowRepeat,
  arrowRight,
  arrowRightShort,
  arrowUpRight,
  asterisk,
  bell,
  bodyText,
  boxArrowUp,
  boxArrowUpRight,
  boxes,
  braces,
  calendar,
  calendarEvent,
  calendarEventFill,
  cardChecklist,
  cardHeading,
  caretDown,
  caretUp,
  chatLeftText,
  chatSquareDots,
  check,
  check2All,
  checkAll,
  checkCircle,
  checkCircleFill,
  checkLg,
  chevronDoubleLeft,
  chevronDoubleRight,
  chevronRight,
  clipboard,
  clipboardCheck,
  clipboardCheckFill,
  clipboardFill,
  clockHistory,
  dash,
  dashCircle,
  diagram3,
  dice5,
  doorOpen,
  download,
  envelope,
  envelopeAt,
  envelopeAtFill,
  exclamationCircleFill,
  exclamationTriangle,
  exclamationTriangleFill,
  eye,
  fileEarmark,
  fileEarmarkCheck,
  fileEarmarkFill,
  fileEarmarkLock,
  fileEarmarkMinus,
  fileEarmarkRichtext,
  fileText,
  files,
  filter,
  folder,
  folderFill,
  funnel,
  gear,
  google,
  grid,
  gripVertical,
  hash,
  hddStack,
  house,
  infoCircle,
  journals,
  link,
  listNested,
  listTask,
  listUl,
  microsoft,
  nodePlus,
  pencil,
  people,
  peopleFill,
  person,
  personCircle,
  personFill,
  personFillLock,
  personLock,
  personSquare,
  playFill,
  plus,
  plusCircle,
  printer,
  questionCircle,
  scissors,
  search,
  send,
  slashCircle,
  sliders2Vertical,
  sortAlphaDown,
  sortAlphaUpAlt,
  stack,
  stars,
  tag,
  tagFill,
  tags,
  textIndentLeft,
  textLeft,
  threeDots,
  threeDotsVertical,
  trash,
  uiRadios,
  unlock,
  upcScan,
  windowStack,
  x,
  xCircle,
  xLg,
} from 'ngx-bootstrap-icons'
import { ColorSliderModule } from 'ngx-color/slider'
import { CookieService } from 'ngx-cookie-service'
import { AppRoutingModule } from './app/app-routing.module'
import { AppComponent } from './app/app.component'
import { DirtyDocGuard } from './app/guards/dirty-doc.guard'
import { DirtySavedViewGuard } from './app/guards/dirty-saved-view.guard'
import { PermissionsGuard } from './app/guards/permissions.guard'
import { withApiVersionInterceptor } from './app/interceptors/api-version.interceptor'
import { withCsrfInterceptor } from './app/interceptors/csrf.interceptor'
import { DocumentTitlePipe } from './app/pipes/document-title.pipe'
import { FilterPipe } from './app/pipes/filter.pipe'
import { UsernamePipe } from './app/pipes/username.pipe'
import { SettingsService } from './app/services/settings.service'
import { LocalizedDateParserFormatter } from './app/utils/ngb-date-parser-formatter'
import { ISODateAdapter } from './app/utils/ngb-iso-date-adapter'

import localeAf from '@angular/common/locales/af'
import localeAr from '@angular/common/locales/ar'
import localeBe from '@angular/common/locales/be'
import localeBg from '@angular/common/locales/bg'
import localeCa from '@angular/common/locales/ca'
import localeCs from '@angular/common/locales/cs'
import localeDa from '@angular/common/locales/da'
import localeDe from '@angular/common/locales/de'
import localeEl from '@angular/common/locales/el'
import localeEnGb from '@angular/common/locales/en-GB'
import localeEs from '@angular/common/locales/es'
import localeFa from '@angular/common/locales/fa'
import localeFi from '@angular/common/locales/fi'
import localeFr from '@angular/common/locales/fr'
import localeHu from '@angular/common/locales/hu'
import localeId from '@angular/common/locales/id'
import localeIt from '@angular/common/locales/it'
import localeJa from '@angular/common/locales/ja'
import localeKo from '@angular/common/locales/ko'
import localeLb from '@angular/common/locales/lb'
import localeNl from '@angular/common/locales/nl'
import localeNo from '@angular/common/locales/no'
import localePl from '@angular/common/locales/pl'
import localePt from '@angular/common/locales/pt'
import localeRo from '@angular/common/locales/ro'
import localeRu from '@angular/common/locales/ru'
import localeSk from '@angular/common/locales/sk'
import localeSl from '@angular/common/locales/sl'
import localeSr from '@angular/common/locales/sr'
import localeSv from '@angular/common/locales/sv'
import localeTr from '@angular/common/locales/tr'
import localeUk from '@angular/common/locales/uk'
import localeVi from '@angular/common/locales/vi'
import localeZh from '@angular/common/locales/zh'
import localeZhHant from '@angular/common/locales/zh-Hant'
import { provideUiTour } from 'ngx-ui-tour-ng-bootstrap'
import { CorrespondentNamePipe } from './app/pipes/correspondent-name.pipe'
import { DocumentTypeNamePipe } from './app/pipes/document-type-name.pipe'
import { StoragePathNamePipe } from './app/pipes/storage-path-name.pipe'

registerLocaleData(localeAf)
registerLocaleData(localeAr)
registerLocaleData(localeBe)
registerLocaleData(localeBg)
registerLocaleData(localeCa)
registerLocaleData(localeCs)
registerLocaleData(localeDa)
registerLocaleData(localeDe)
registerLocaleData(localeEl)
registerLocaleData(localeEnGb)
registerLocaleData(localeEs)
registerLocaleData(localeFa)
registerLocaleData(localeFi)
registerLocaleData(localeFr)
registerLocaleData(localeHu)
registerLocaleData(localeId)
registerLocaleData(localeIt)
registerLocaleData(localeJa)
registerLocaleData(localeKo)
registerLocaleData(localeLb)
registerLocaleData(localeNl)
registerLocaleData(localeNo)
registerLocaleData(localePl)
registerLocaleData(localePt, 'pt-BR')
registerLocaleData(localePt, 'pt-PT')
registerLocaleData(localeRo)
registerLocaleData(localeRu)
registerLocaleData(localeSk)
registerLocaleData(localeSl)
registerLocaleData(localeSr)
registerLocaleData(localeSv)
registerLocaleData(localeTr)
registerLocaleData(localeVi)
registerLocaleData(localeUk)
registerLocaleData(localeZh)
registerLocaleData(localeZhHant)

function initializeApp() {
  const settings = inject(SettingsService)
  return settings.initializeSettings()
}

const icons = {
  airplane,
  archive,
  arrowClockwise,
  arrowCounterclockwise,
  arrowDown,
  arrowDownUp,
  arrowLeft,
  arrowRepeat,
  arrowRight,
  arrowRightShort,
  arrowUpRight,
  asterisk,
  bell,
  braces,
  bodyText,
  boxArrowUp,
  boxArrowUpRight,
  boxes,
  calendar,
  calendarEvent,
  calendarEventFill,
  cardChecklist,
  cardHeading,
  caretDown,
  caretUp,
  chatLeftText,
  chatSquareDots,
  check,
  check2All,
  checkAll,
  checkCircle,
  checkCircleFill,
  checkLg,
  chevronDoubleLeft,
  chevronDoubleRight,
  chevronRight,
  clipboard,
  clipboardCheck,
  clipboardCheckFill,
  clipboardFill,
  clockHistory,
  dash,
  dashCircle,
  diagram3,
  dice5,
  doorOpen,
  download,
  envelope,
  envelopeAt,
  envelopeAtFill,
  exclamationCircleFill,
  exclamationTriangle,
  exclamationTriangleFill,
  eye,
  fileEarmark,
  fileEarmarkCheck,
  fileEarmarkFill,
  fileEarmarkLock,
  fileEarmarkMinus,
  fileEarmarkRichtext,
  files,
  fileText,
  filter,
  folder,
  folderFill,
  funnel,
  gear,
  google,
  grid,
  gripVertical,
  hash,
  hddStack,
  house,
  infoCircle,
  journals,
  link,
  listNested,
  listTask,
  listUl,
  microsoft,
  nodePlus,
  pencil,
  people,
  peopleFill,
  person,
  personCircle,
  personFill,
  personFillLock,
  personLock,
  personSquare,
  playFill,
  plus,
  plusCircle,
  printer,
  questionCircle,
  scissors,
  search,
  send,
  slashCircle,
  sliders2Vertical,
  sortAlphaDown,
  sortAlphaUpAlt,
  stack,
  stars,
  tagFill,
  tag,
  tags,
  textIndentLeft,
  textLeft,
  threeDots,
  threeDotsVertical,
  trash,
  uiRadios,
  unlock,
  upcScan,
  windowStack,
  x,
  xCircle,
  xLg,
}

bootstrapApplication(AppComponent, {
  providers: [
    provideZoneChangeDetection(),
    importProvidersFrom(
      BrowserModule,
      AppRoutingModule,
      NgbModule,
      FormsModule,
      ReactiveFormsModule,
      NgSelectModule,
      ColorSliderModule,
      DragDropModule,
      NgxBootstrapIconsModule.pick(icons)
    ),
    provideAppInitializer(initializeApp),
    DatePipe,
    CookieService,
    FilterPipe,
    DocumentTitlePipe,
    { provide: NgbDateAdapter, useClass: ISODateAdapter },
    { provide: NgbDateParserFormatter, useClass: LocalizedDateParserFormatter },
    PermissionsGuard,
    DirtyDocGuard,
    DirtySavedViewGuard,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    provideHttpClient(
      withInterceptorsFromDi(),
      withInterceptors([withCsrfInterceptor, withApiVersionInterceptor]),
      withFetch()
    ),
    provideUiTour({
      enableBackdrop: true,
      backdropConfig: {
        offset: 10,
      },
      prevBtnTitle: $localize`Prev`,
      nextBtnTitle: $localize`Next`,
      endBtnTitle: $localize`End`,
      isOptional: true,
      useLegacyTitle: true,
    }),
  ],
}).catch((err) => console.error(err))
