import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WidgetFrameComponent } from './widget-frame.component';

describe('WidgetFrameComponent', () => {
  let component: WidgetFrameComponent;
  let fixture: ComponentFixture<WidgetFrameComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ WidgetFrameComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(WidgetFrameComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
