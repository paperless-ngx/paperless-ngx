import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ConsumerStatusWidgetComponent } from './consumer-status-widget.component';

describe('ConsumerStatusWidgetComponent', () => {
  let component: ConsumerStatusWidgetComponent;
  let fixture: ComponentFixture<ConsumerStatusWidgetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ConsumerStatusWidgetComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ConsumerStatusWidgetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
