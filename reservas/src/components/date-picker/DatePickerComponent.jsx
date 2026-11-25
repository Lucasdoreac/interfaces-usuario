import React from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

const DatePickerComponent = ({ selectedDate, onDateChange }) => {
  return (
    <div className="datepicker-component">
      <DatePicker
        selected={selectedDate}
        onChange={onDateChange}
        minDate={new Date()}
        dateFormat="dd/MM/yyyy"
        showMonthDropdown
        showYearDropdown
        dropdownMode="select"
      />
    </div>
  );
};

export default DatePickerComponent;
