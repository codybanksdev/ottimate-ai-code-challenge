import React from 'react';
import './App.css';
import VendorList from './VendorList';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Accounts Payable</h1>
        <p>Harbor &amp; Vine Restaurant Group · vendor balances</p>
      </header>
      <main className="App-main">
        <VendorList />
      </main>
    </div>
  );
}

export default App;
