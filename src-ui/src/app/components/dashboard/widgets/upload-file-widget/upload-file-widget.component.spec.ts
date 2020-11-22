import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UploadFileWidgetComponent } from './upload-file-widget.component';

describe('UploadFileWidgetComponent', () => {
  let component: UploadFileWidgetComponent;
  let fixture: ComponentFixture<UploadFileWidgetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ UploadFileWidgetComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(UploadFileWidgetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
